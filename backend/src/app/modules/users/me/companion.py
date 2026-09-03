from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

import config
from src.app.modules.auth.dependencies import get_current_user
from src.app.services.ai.companion import service
from src.app.services.ai.companion.schemas import Action, Settings
from src.app.services.ai.security import ensure_app_ai_access
from src.app.services.app_integrity.service import verify_app_integrity_request
from src.database import get_db
from src.database.models import User

companion_router = APIRouter(prefix="/ai-chat/companion", tags=["ai_companion"])


async def native_access(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not config.AI_COMPANION_ENABLED and request.method != "DELETE":
        raise HTTPException(404, "Сопровождение пока недоступно")
    platform = (request.headers.get("x-app-integrity-platform") or "").lower()
    if platform not in {"ios", "android"}:
        raise HTTPException(403, "Сопровождение доступно только в мобильном приложении")
    await verify_app_integrity_request(request, action="ai-companion", db=db, current_user=user, force_enforce=True)
    await ensure_app_ai_access(db, request=request, user=user)
    return user


@companion_router.get("/availability")
async def availability(user: User = Depends(get_current_user)):
    return {"available": config.AI_COMPANION_ENABLED, "consent_version": config.AI_COMPANION_CONSENT_VERSION}


@companion_router.get("")
async def state(user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    await service.ensure_default_profile(db, user.id)
    await db.commit()
    return await service.get_state(db, user.id)


@companion_router.post("/actions")
async def action(payload: Action, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    try:
        result = await service.apply_action(db, user.id, payload)
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
    zone = ZoneInfo(Settings.model_validate(profile.settings).timezone)
    return tuple(datetime.combine(d, time.min, zone).astimezone(timezone.utc) for d in (from_date, to_date))


@companion_router.get("/entries")
async def entries(from_date: date, to_date: date, kind: str | None = None, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    if kind is not None and kind not in {"meal", "weight", "wellbeing"}:
        raise HTTPException(422, "Неизвестный тип записи")
    start, end = await bounds(db, user.id, from_date, to_date)
    return {"entries": [service.dump(e) for e in await service.entries_for(db, user.id, start, end, kind)]}


@companion_router.get("/summary")
async def summary(from_date: date, to_date: date, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    start, end = await bounds(db, user.id, from_date, to_date)
    return await service.summary_for(db, user.id, start, end)


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


@companion_router.post("/messages")
async def message(request: Request, text: str = Form(...), client_request_id: str = Form(..., min_length=8, max_length=64), attachments: list[UploadFile] | None = File(None), user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    import asyncio
    from src.app.services.cache import get_cache_service
    from src.app.services.ai.chat import send_user_chat_message
    from src.app.services.platform_availability import is_commerce_blocked
    from src.integrations.ai import get_professor_client
    from .schemas.ai_chat import AIChatResponse, AIChatTurnMetaRead
    from src.app.services.rate_limit import enforce_rate_limit
    from src.app.services.ai.security import record_app_ai_activity
    await enforce_rate_limit(request, scope="ai_companion_message", limit=10, window_seconds=60, key=str(user.id))
    if len(text) > 20000:
        raise HTTPException(422, "Сообщение слишком длинное")
    if not text.strip():
        raise HTTPException(422, "Сообщение пустое")
    profile = await service.ensure_default_profile(db, user.id)
    await db.commit()
    if profile is None or not profile.enabled:
        raise HTTPException(403, "Сопровождение отключено")
    await service.require_chat_consent(db, user.id, profile)
    cache = get_cache_service().client
    if cache is None:
        raise HTTPException(503, "Чат временно недоступен; ручные записи работают")
    lock = cache.lock(f"ai_companion:turn:{user.id}", timeout=600, blocking=False)
    from redis.exceptions import RedisError
    try:
        acquired = await lock.acquire()
    except RedisError as error:
        raise HTTPException(503, "AI временно недоступен; ручные записи работают") from error
    if not acquired:
        raise HTTPException(409, "Предыдущее сообщение ещё обрабатывается")
    try:
        await record_app_ai_activity(db, request=request, user=user, event_type="message_requested", details={"message_length": len(text), "attachments_count": len(attachments or []), "mode": "companion"})
        async with asyncio.timeout(540):
            result = await send_user_chat_message(db, user=user, text=text.strip(), attachments=attachments, professor_client=get_professor_client(), allow_commerce=not is_commerce_blocked(request.headers, "/api/v1/products", "GET"), companion_profile=profile, client_request_id=client_request_id)
        return AIChatResponse(chat=result.chat, last_turn=AIChatTurnMetaRead(**result.turn_meta) if result.turn_meta else None)
    finally:
        try:
            if await lock.owned():
                await lock.release()
        except RedisError:
            pass  # The finite lock lease releases itself; do not mask the response.


@companion_router.get("/supply")
async def supply(request: Request, days: int = Query(default=30, ge=1, le=90), user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    from src.app.services.platform_availability import is_commerce_blocked
    if is_commerce_blocked(request.headers, "/api/v1/products", "GET"):
        raise HTTPException(403, "Каталог и покупки недоступны на этой платформе")
    return await service.supply_for(db, user.id, days)


@companion_router.delete("")
async def erase(confirm: bool = False, user: User = Depends(native_access), db: AsyncSession = Depends(get_db)):
    if not confirm:
        raise HTTPException(422, "Подтвердите удаление записей и сообщений сопровождения")
    await service.erase_companion(db, user.id)
    await db.commit()
    return {"ok": True, "external_cleanup": "queued"}
