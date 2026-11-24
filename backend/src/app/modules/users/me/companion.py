from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import ValidationError, Field
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession

import config
from src.app.modules.auth.dependencies import get_current_user
from src.app.services.ai.companion import service
from src.app.services.ai.companion.schemas import Action, EntryData, Settings, StrictModel
from src.app.services.ai.companion.food_suggestions import FoodSuggestionRead, MealSuggestionContext
from src.app.services.ai.companion.workout_drafts import WorkoutDraftRead, WorkoutDraftRequest
from src.app.services.ai.companion.mentor import FavoriteMealsRead, MentorDashboard, ProgressSummary, dashboard
from src.app.services.ai.companion.photos import ProgressPhotosRead, serialize_entries
from src.app.services.ai.companion.timezones import normalize_timezone, timezone_info
from src.app.services.ai.security import ensure_app_ai_access
from src.app.services.ai.data_consent import require_ai_data_consent
from src.app.services.app_integrity.service import verify_app_integrity_request
from src.database import get_db
from src.database.models import User
from .schemas.ai_chat import AIChatResponse

companion_router = APIRouter(prefix="/ai-chat/companion", tags=["ai_companion"])


def device_timezone(request):
    value = request.headers.get("x-device-timezone")
    if value is None:
        return None  # Backward-compatible with already-installed clients.
    try:
        if len(value) > 100:
            raise ValueError("Invalid device timezone")
        return normalize_timezone(value)
    except ValueError as error:
        raise HTTPException(422, "Не удалось определить часовой пояс устройства") from error


async def native_access(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not config.AI_COMPANION_ENABLED and request.method != "DELETE":
        raise HTTPException(404, "Сопровождение пока недоступно")
    platform = (request.headers.get("x-app-integrity-platform") or "").lower()
    if platform not in {"ios", "android"}:
        raise HTTPException(403, "Сопровождение доступно только в мобильном приложении")
    await verify_app_integrity_request(request, action="ai-companion", db=db, current_user=user)
    await ensure_app_ai_access(db, request=request, user=user)
    if request.method != "DELETE" and (zone := device_timezone(request)) is not None:
        await service.sync_device_timezone(db, user.id, zone)
        await db.commit()
    return user


@companion_router.get("/availability")
async def availability(request: Request, user: User = Depends(get_current_user)):
    return {"available": config.AI_COMPANION_ENABLED, "consent_version": config.AI_COMPANION_CONSENT_VERSION}


@companion_router.get("")
async def state(request: Request, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    await service.ensure_default_profile(db, user.id, device_timezone(request))
    await db.commit()
    return await service.get_state(db, user.id)


@companion_router.post("/timezone")
async def sync_timezone(user: User = Depends(native_access)):
    # native_access updates an existing profile only. Do not enable a feature,
    # create health records or grant consent just because the app was opened.
    return {"ok": True}


@companion_router.post("/actions")
async def action(payload: Action, request: Request, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    if payload.kind.startswith("dialogue_") and not config.AI_COMPANION_DIALOGUE_ENABLED:
        raise HTTPException(404, "Обновление диалога пока недоступно")
    try:
        if payload.settings is not None and (zone := device_timezone(request)) is not None:
            payload.settings.timezone = zone  # A stale open form cannot undo travel.
        result = await service.apply_action(db, user.id, payload, allow_commerce=True)
        await db.commit()
    except (ValidationError, ValueError) as error:
        await db.rollback()
        raise HTTPException(422, str(error)) from error
    except Exception:
        await db.rollback()
        raise
    return {**result, "state": await service.get_state(db, user.id)}


async def bounds(db, user_id, from_date, to_date):
    if not 0 < (to_date - from_date).days <= 90:
        raise HTTPException(422, "Период должен составлять 1–90 дней")
    profile = await service.profile_for(db, user_id)
    if profile is None:
        raise HTTPException(404, "Сопровождение не включено")
    zone = timezone_info(Settings.model_validate(profile.settings).timezone)
    return tuple(datetime.combine(d, time.min, zone).astimezone(timezone.utc) for d in (from_date, to_date))


@companion_router.get("/entries")
async def entries(from_date: date, to_date: date, kind: str | None = None, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    if kind is not None and kind not in {"meal", "weight", "wellbeing", "workout", "measurement", "progress_photo", "water"}:
        raise HTTPException(422, "Неизвестный тип записи")
    start, end = await bounds(db, user.id, from_date, to_date)
    return {"entries": await serialize_entries(db, user.id, await service.entries_for(db, user.id, start, end, kind))}


@companion_router.get("/progress-photos", response_model=ProgressPhotosRead)
async def progress_photos(from_date: date, to_date: date, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    await service.require_consent(db, user.id)
    start, end = await bounds(db, user.id, from_date, to_date)
    rows = await service.entries_for(db, user.id, start, end, "progress_photo", limit=201)
    return {"entries": await serialize_entries(db, user.id, rows[:200]), "limit": 200, "may_have_more": len(rows) > 200}


@companion_router.get("/favorite-meals", response_model=FavoriteMealsRead)
async def favorite_meals(user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    return await service.favorite_meals_for(db, user.id)


@companion_router.get("/summary", response_model=ProgressSummary)
async def summary(from_date: date, to_date: date, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    start, end = await bounds(db, user.id, from_date, to_date)
    return await service.summary_for(db, user.id, start, end)


@companion_router.get("/mentor", response_model=MentorDashboard | None)
async def mentor(user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    return await dashboard(db, user.id)


@companion_router.get("/events")
async def events(from_date: date, to_date: date, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from src.database.models.ai.companion import AICompanionEvent
    start, end = await bounds(db, user.id, from_date, to_date)
    rows = list((await db.execute(select(AICompanionEvent).where(AICompanionEvent.user_id == user.id, AICompanionEvent.scheduled_at >= start, AICompanionEvent.scheduled_at < end, AICompanionEvent.status != "cancelled").order_by(AICompanionEvent.scheduled_at).limit(200))).scalars().all())
    return {"events": [service.dump(row) for row in rows], "limit": 200}


@companion_router.get("/nutrition")
async def nutrition(user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    return await service.nutrition_suggestion(db, user.id)


async def _message(request, text, client_request_id, attachments, dialogue_protocol, user, db, *, meal_estimate=False, nutrition_help=None, workout_request=None):
    if dialogue_protocol != 2:
        raise HTTPException(426, detail={"code": "mentor_client_update_required", "message": "Обновите приложение для работы с наставником."})
    await require_ai_data_consent(db, user.id)
    import asyncio
    from src.app.services.cache import get_cache_service
    from src.app.services.ai.chat import send_user_chat_message
    from src.integrations.ai import get_professor_client
    from .schemas.ai_chat import AIChatResponse, AIChatTurnMetaRead
    from src.app.services.rate_limit import enforce_rate_limit
    from src.app.services.ai.security import record_app_ai_activity
    await enforce_rate_limit(request, scope="ai_companion_message", limit=10, window_seconds=60, key=str(user.id))
    if len(text) > 20000:
        raise HTTPException(422, "Сообщение слишком длинное")
    if not text.strip():
        raise HTTPException(422, "Сообщение пустое")
    profile = await service.ensure_default_profile(db, user.id, device_timezone(request))
    await db.commit()
    if profile is None or not profile.enabled:
        raise HTTPException(403, "Сопровождение отключено")
    await service.require_chat_consent(db, user.id, profile)
    cache = get_cache_service().client
    if cache is None:
        raise HTTPException(503, "Чат временно недоступен; попробуйте отправить сообщение ещё раз")
    lock = cache.lock(f"ai_companion:turn:{user.id}", timeout=600, blocking=False)
    from redis.exceptions import RedisError
    try:
        acquired = await lock.acquire()
    except RedisError as error:
        raise HTTPException(503, "AI временно недоступен; попробуйте отправить сообщение ещё раз") from error
    if not acquired:
        raise HTTPException(409, "Предыдущее сообщение ещё обрабатывается")
    try:
        await record_app_ai_activity(db, request=request, user=user, event_type="message_requested", details={"message_length": len(text), "attachments_count": len(attachments or []), "mode": "companion"})
        async with asyncio.timeout(540):
            result = await send_user_chat_message(db, user=user, text=text.strip(), attachments=attachments, professor_client=get_professor_client(), allow_commerce=False, companion_profile=profile, client_request_id=client_request_id, dialogue_protocol=2, **({"meal_estimate": True, **({"nutrition_help": nutrition_help} if nutrition_help else {})} if meal_estimate else {}), **({"workout_request": workout_request} if workout_request is not None else {}))
        if workout_request is not None:
            if result.workout_draft is None:
                raise HTTPException(409, "Не удалось восстановить черновик. Повторите запрос.")
            return WorkoutDraftRead.model_validate(result.workout_draft)
        if meal_estimate:
            if result.meal_estimate is None:
                raise HTTPException(409, "Не удалось восстановить расчёт. Попробуйте ещё раз.")
            return MealEstimateRead.model_validate(result.meal_estimate)
        return AIChatResponse(chat=result.chat, last_turn=AIChatTurnMetaRead(**result.turn_meta) if result.turn_meta else None)
    finally:
        try:
            if await lock.owned():
                await lock.release()
        except RedisError:
            pass  # The finite lock lease releases itself; do not mask the response.


class MealEstimateRead(StrictModel):
    entry: EntryData | None = None
    message: str
    suggestions: list[FoodSuggestionRead] = Field(default_factory=list, max_length=3)
    next_meal: MealSuggestionContext | None = None


@companion_router.post("/workout-draft", response_model=WorkoutDraftRead)
async def workout_draft(request: Request, payload: str = Form(..., max_length=200000), client_request_id: str = Form(..., min_length=8, max_length=64), attachments: list[UploadFile] | None = File(None), user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    try:
        draft_request = WorkoutDraftRequest.model_validate_json(payload)
    except ValidationError as error:
        raise HTTPException(422, "Проверьте данные программы и расписание") from error
    if len(attachments or []) > 3 or any(not (photo.content_type or "").lower().startswith("image/") for photo in attachments or []):
        raise HTTPException(422, "Можно добавить до трёх фотографий")
    # The shared pipeline validates image bytes, stores private attachments and registers
    # provider resources for erasure. No plan/entry action runs until the user saves.
    return await _message(request, draft_request.text or "Составить план тренировок", client_request_id, attachments, 2, user, db, workout_request=draft_request)


@companion_router.post("/messages")
async def message(request: Request, text: str = Form(...), client_request_id: str = Form(..., min_length=8, max_length=64), attachments: list[UploadFile] | None = File(None), dialogue_protocol: int | None = Form(None), user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    return await _message(request, text, client_request_id, attachments, dialogue_protocol, user, db)


@companion_router.get("/messages", response_model=AIChatResponse)
async def read_messages(user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    from src.database.crud.ai.chat import get_ai_chat_by_user_id
    profile = await service.profile_for(db, user.id)
    if profile is None or not profile.enabled:
        raise HTTPException(403, "Сопровождение отключено")
    await service.require_chat_consent(db, user.id, profile)
    return AIChatResponse(chat=await get_ai_chat_by_user_id(db, user.id, scope="mentor"), last_turn=None)


@companion_router.post("/meal-estimate", response_model=MealEstimateRead)
async def meal_estimate(request: Request, text: str = Form("", max_length=4000), client_request_id: str = Form(..., min_length=8, max_length=64), attachments: list[UploadFile] | None = File(None), user: User = Depends(native_access), db: AsyncSession = Depends(get_db), photo_attachment_id: int | None = Form(None, gt=0), original_id: int | None = Form(None, gt=0), original_version: int | None = Form(None, gt=0),
                        meal_type: Literal["breakfast", "lunch", "dinner", "extra"] | None = Form(None), meal_key: str | None = Form(None, max_length=64)):
    if isinstance(photo_attachment_id, int):
        from io import BytesIO
        from src.app.services.ai.companion.photos import owned_photos
        from starlette.datastructures import Headers
        photos = await owned_photos(db, user.id, [photo_attachment_id])
        photo = photos.get(photo_attachment_id)
        if photo is None:
            raise HTTPException(422, "Фото больше недоступно. Выберите другое фото.")
        attachments = [*(attachments or []), UploadFile(BytesIO(photo.path.read_bytes()), filename=photo.original_filename or photo.filename, headers=Headers({"content-type": photo.mime_type}))]
    if not text.strip() and not attachments:
        raise HTTPException(422, "Опишите еду или добавьте фото")
    result = await _message(request, text.strip() or "Оцените КБЖУ еды на фото.", client_request_id, attachments, 2, user, db, meal_estimate=True)
    result = MealEstimateRead.model_validate(result)
    if attachments and result.entry and result.entry.food_photo_attachment_ids:
        from src.app.services.ai.companion.mobile_push import photo_ready
        await photo_ready(db, user.id, client_request_id, original_id, original_version, meal_type, meal_key)
        await db.commit()
    return result


@companion_router.get("/meals")
async def meal_library(user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    from src.app.services.ai.companion.meals import library
    return await library(db, user.id)


@companion_router.get("/workouts")
async def workout_library(from_date: date, to_date: date, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from src.database.models.ai.companion import AICompanionEntry
    await service.require_consent(db, user.id)
    start, end = await bounds(db, user.id, from_date, to_date)
    base = select(AICompanionEntry).where(AICompanionEntry.user_id == user.id, AICompanionEntry.kind == "workout", AICompanionEntry.occurred_at <= service.now_utc())
    ordered = base.order_by(AICompanionEntry.occurred_at.desc(), AICompanionEntry.id.desc())
    recent = list((await db.execute(ordered.limit(201))).scalars())
    running = list((await db.execute(ordered.where(AICompanionEntry.data["workout"]["status"].as_string() == "in_progress").limit(51))).scalars())
    period = await service.entries_for(db, user.id, start, min(end, service.now_utc() + timedelta(microseconds=1)), "workout", limit=1001)
    rows = {row.id: row for row in [*recent[:200], *running[:50], *period[:1000]]}
    return {"entries": [service.dump(row) for row in sorted(rows.values(), key=lambda row: (row.occurred_at, row.id), reverse=True)], "may_have_more": len(recent) > 200 or len(running) > 50 or len(period) > 1000}


@companion_router.post("/nutrition-help", response_model=MealEstimateRead)
async def nutrition_help(request: Request, mode: Literal["suggest", "product"] = Form(...), text: str = Form("", max_length=4000), client_request_id: str = Form(..., min_length=8, max_length=64), attachments: list[UploadFile] | None = File(None), user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    if not text.strip() and not attachments:
        raise HTTPException(422, "Напишите вопрос или добавьте фото")
    return await _message(request, text.strip() or "Расскажите о продукте на фото.", client_request_id, attachments, 2, user, db, meal_estimate=True, nutrition_help=mode)


@companion_router.get("/supply")
async def supply(request: Request, days: int = Query(default=30, ge=1, le=90), user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    return await service.supply_for(db, user.id, days)


class DialogueRequest(StrictModel):
    request_key: str = Field(min_length=8, max_length=64)
    kind: Literal["intro", "course", "nutrition", "progress"]
    days: Literal[7, 30] = 7


@companion_router.post("/dialogue")
async def dialogue_request(payload: DialogueRequest, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from src.database.models.ai.companion import AICompanionOperation
    from src.app.services.ai.companion import dialogue
    from src.app.services.ai.companion.dialogue_tools import quick_report
    if not config.AI_COMPANION_DIALOGUE_ENABLED:
        raise HTTPException(404, "Обновление диалога пока недоступно")
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    profile = await service.profile_for(db, user.id)
    if profile is None or not profile.enabled:
        raise HTTPException(403, "Сопровождение отключено")
    receipt = (await db.execute(select(AICompanionOperation).where(AICompanionOperation.user_id == user.id, AICompanionOperation.request_key == payload.request_key))).scalar_one_or_none()
    fingerprint = dialogue.digest(payload.model_dump())
    if receipt is not None:
        if receipt.fingerprint != fingerprint:
            raise HTTPException(409, "Ключ запроса уже использован")
        return {"ok": True}
    if payload.kind == "intro":
        await dialogue.introduce(db, user.id)
    else:
        await service.require_consent(db, user.id)
        body = await quick_report(db, user.id, payload.kind, payload.days)
        await dialogue.say(db, user.id, body)
    db.add(AICompanionOperation(user_id=user.id, request_key=payload.request_key, fingerprint=fingerprint, result={"ok": True}))
    await db.commit()
    return {"ok": True}


@companion_router.delete("")
async def erase(confirm: bool = False, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    if not confirm:
        raise HTTPException(422, "Подтвердите удаление записей и сообщений сопровождения")
    await service.erase_companion(db, user.id)
    await db.commit()
    return {"ok": True, "external_cleanup": "queued"}

class NoticeRequest(StrictModel):
    profile: int = Field(gt=0)
    key: str = Field(min_length=1, max_length=200)
    action: str | None = Field(default=None, max_length=40)
    minutes: int = Field(default=30, ge=1, le=720)
    ml: int | None = Field(default=None, gt=0, le=10000)
    score: int | None = Field(default=None, ge=1, le=5)
    start_workout: bool = False
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)


@companion_router.post("/mobile-notice")
async def mobile_notice(payload: NoticeRequest, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    from src.app.services.ai.companion.push_actions import resolve
    result = await resolve(db, user.id, payload.profile, payload.key, payload.action, payload.minutes, payload.ml, payload.score, payload.start_workout, payload.duration_minutes)
    await db.commit()
    return result

@companion_router.post("/meal-estimate/{request_key}/seen")
async def estimate_seen(request_key: str, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    import hashlib
    from sqlalchemy import select
    from src.database.models.ai.companion import AICompanionReminder
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    await service.require_consent(db, user.id)
    key = "photo:" + hashlib.sha256(request_key.encode()).hexdigest()
    row = await db.scalar(select(AICompanionReminder).where(AICompanionReminder.user_id == user.id, AICompanionReminder.dedupe_key == key))
    if row and row.status == "pending":
        row.context = {**(row.context or {}), "photo_seen": True}
        row.status = "cancelled"
    await db.commit()
    return {"ok": True}
