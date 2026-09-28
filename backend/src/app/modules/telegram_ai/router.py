"""Telegram transport over the existing companion domain, with signed service requests."""
import asyncio
import base64
import binascii
from datetime import timedelta
from io import BytesIO
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import Field
from sqlalchemy import func, select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

import config
from src.database import get_db
from src.database.models import AIMessage, User
from src.database.models.ai.companion import AICompanionReminder
from src.integrations.ai import get_professor_client
from src.integrations.ai.enums import BotModel
from src.app.services.ai.companion import dialogue, service
from src.app.services.ai.companion.schemas import Action, Settings, StrictModel
from src.app.services.ai.companion.timezones import normalize_timezone
from src.app.services.ai.companion.dialogue_tools import quick_report
from src.app.services.cache import get_cache_service
from .auth import require_bot
from .catalog import CatalogRequest, read_catalog
from .profile import router as profile_router
from .journal import router as journal_router

telegram_ai_router = APIRouter(prefix="/integrations/telegram-ai", tags=["telegram_ai"], dependencies=[Depends(require_bot)])

telegram_ai_router.include_router(profile_router)
telegram_ai_router.include_router(journal_router)


class Identity(StrictModel):
    telegram_user_id: int = Field(gt=0, le=2**53)


class Start(Identity):
    request_key: str = Field(min_length=8, max_length=64)
    adult_confirmed: bool
    timezone: str = Field(default="Europe/Moscow", max_length=100)


class AttachmentInput(StrictModel):
    filename: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=14_000_000)
    content_type: str = Field(max_length=100)


class MessageInput(Identity):
    text: str = Field(min_length=1, max_length=20000)
    request_key: str = Field(min_length=8, max_length=64)
    model: BotModel = BotModel.FREE
    attachments: list[AttachmentInput] = Field(default_factory=list, max_length=8)


class CardInput(Identity):
    message_id: int = Field(gt=0)
    card_id: str = Field(min_length=1, max_length=120)
    kind: Literal["dialogue_confirm", "dialogue_cancel", "dialogue_undo", "dialogue_edit"]
    request_key: str = Field(min_length=8, max_length=64)


class Control(Identity):
    kind: Literal["progress", "nutrition", "course", "stop", "eligibility", "timezone", "erase"]
    days: Literal[7, 30] = 7
    confirmed: bool = False
    value: str = Field(default="", max_length=100)
    request_key: str = Field(min_length=8, max_length=64)


class Reminders(Identity):
    after_id: int = Field(default=0, ge=0)


async def owned_user(db, telegram_user_id, *, create=False):
    if not config.AI_COMPANION_ENABLED or not config.AI_COMPANION_DIALOGUE_ENABLED:
        raise HTTPException(503, "Наставник временно недоступен")
    # Serialize identity creation without merging on unverified phone/name.
    await db.execute(sql_text("SELECT pg_advisory_xact_lock(:id)"), {"id": -telegram_user_id})
    user = (await db.execute(select(User).where(User.telegram_user_id == telegram_user_id))).scalar_one_or_none()
    if user is None and create:
        user = User(telegram_user_id=telegram_user_id, name="", surname="", password_hash="!telegram-only:" + uuid4().hex)
        db.add(user)
        await db.flush()
    if user is None:
        raise HTTPException(404, "Сначала откройте наставника командой /mentor")
    if not user.is_active:
        raise HTTPException(403, "Аккаунт отключён")
    return user


async def active_profile(db, user):
    profile = await service.profile_for(db, user.id)
    if profile is None or not profile.enabled:
        raise HTTPException(403, "Сопровождение отключено. Откройте /mentor")
    await service.require_consent(db, user.id)
    return profile


def public_message(message):
    # Never expose action signatures, internal guards or undo snapshots to Telegram.
    cards = [{k: c[k] for k in ("id", "kind", "summary", "state", "operation", "changes", "error") if k in c}
             for c in (message.context_json or {}).get("dialogue_cards", [])]
    return {"message_id": message.id, "text": message.text, "cards": cards}


@telegram_ai_router.post("/catalog")
async def catalog(payload: CatalogRequest, db: AsyncSession = Depends(get_db)):
    return await read_catalog(db, payload)


@telegram_ai_router.post("/mentor/start")
async def start(payload: Start, db: AsyncSession = Depends(get_db)):
    if not payload.adult_confirmed:
        raise HTTPException(422, "Нужно подтверждение 18+ и согласия")
    try:
        zone = normalize_timezone(payload.timezone)
    except ValueError as error:
        raise HTTPException(422, "Неизвестный часовой пояс") from error
    user = await owned_user(db, payload.telegram_user_id, create=True)
    await service.apply_action(db, user.id, Action(kind="enable", request_key=payload.request_key,
        adult_confirmed=True, consent_version=config.AI_COMPANION_CONSENT_VERSION, settings=Settings(timezone=zone)))
    await db.commit()
    state = await service.get_state(db, user.id)
    latest = (await db.execute(select(func.max(AIMessage.id)).where(AIMessage.user_id == user.id))).scalar() or 0
    return {"ok": True, "timezone": state["profile"]["settings"]["timezone"], "after_id": latest}


@telegram_ai_router.post("/mentor/messages")
async def message(payload: MessageInput, request: Request, db: AsyncSession = Depends(get_db)):
    from src.app.services.ai.chat import send_user_chat_message
    from src.app.services.rate_limit import enforce_rate_limit
    user = await owned_user(db, payload.telegram_user_id)
    await enforce_rate_limit(request, scope="telegram_mentor", limit=10, window_seconds=60, key=str(user.id))
    profile = await active_profile(db, user)
    await db.commit()  # Do not hold the identity lock during an AI call.
    cache = get_cache_service().client
    if cache is None:
        raise HTTPException(503, "Наставник временно недоступен")
    lock = cache.lock(f"ai_companion:turn:{user.id}", timeout=600, blocking=False)
    if not await lock.acquire():
        raise HTTPException(409, "Предыдущее сообщение ещё обрабатывается")
    uploads = []
    try:
        total = 0
        for item in payload.attachments:
            try:
                data = base64.b64decode(item.content, validate=True)
            except (ValueError, binascii.Error) as error:
                raise HTTPException(422, "Некорректное вложение") from error
            total += len(data)
            if total > 20_000_000:
                raise HTTPException(413, "Вложения слишком большие")
            uploads.append(UploadFile(filename=item.filename, file=BytesIO(data), headers=Headers({"content-type": item.content_type})))
        async with asyncio.timeout(540):
            result = await send_user_chat_message(db, user=user, text=payload.text, attachments=uploads,
                professor_client=get_professor_client(), allow_commerce=True, companion_profile=profile,
                client_request_id="tg:" + payload.request_key[:61], dialogue_protocol=2,
                telegram_transport=True, bot_model_override=payload.model)
        source = (await db.execute(select(AIMessage).where(AIMessage.user_id == user.id, AIMessage.client_request_id == "tg:" + payload.request_key[:61]))).scalar_one()
        next_user_id = (await db.execute(select(func.min(AIMessage.id)).where(AIMessage.user_id == user.id, AIMessage.id > source.id, AIMessage.sender == "user"))).scalar()
        replies = list((await db.execute(select(AIMessage).where(AIMessage.user_id == user.id, AIMessage.id > source.id, AIMessage.id < (next_user_id or 2**63-1), AIMessage.sender == "ai").order_by(AIMessage.id))).scalars())
        replies = [m for m in replies if not (m.context_json or {}).get("reminder_id")]
        return {"messages": [public_message(m) for m in replies], "usage": result.turn_meta or {}}
    finally:
        for upload in uploads:
            await upload.close()
        try:
            if await lock.owned():
                await lock.release()
        except Exception:
            pass


@telegram_ai_router.post("/mentor/actions")
async def action(payload: CardInput, db: AsyncSession = Depends(get_db)):
    user = await owned_user(db, payload.telegram_user_id)
    await active_profile(db, user)
    message = await db.get(AIMessage, payload.message_id)
    if message is None or message.user_id != user.id:
        raise HTTPException(404, "Карточка не найдена")
    card = next((c for c in (message.context_json or {}).get("dialogue_cards", []) if c["id"] == payload.card_id), None)
    if card is None:
        raise HTTPException(404, "Карточка не найдена")
    await service.apply_action(db, user.id, Action(kind=payload.kind, request_key=payload.request_key,
        message_id=message.id, action_id=card["id"], action_token=card["action_token"]))
    await db.commit()
    await db.refresh(message)
    return public_message(message)


@telegram_ai_router.post("/mentor/control")
async def control(payload: Control, db: AsyncSession = Depends(get_db)):
    user = await owned_user(db, payload.telegram_user_id)
    profile = await active_profile(db, user)
    if payload.kind == "erase":
        if not payload.confirmed:
            raise HTTPException(422, "Подтвердите удаление")
        await service.erase_companion(db, user.id)
        body = "Учёт удалён. Очистка ресурсов ИИ поставлена в очередь. Сообщения в Telegram можно удалить в самом Telegram."
    elif payload.kind in {"progress", "nutrition", "course"}:
        body = await quick_report(db, user.id, payload.kind, payload.days)
    else:
        settings = Settings.model_validate(profile.settings)
        if payload.kind == "stop":
            settings.course_reminders = settings.supply_reminders = False
            settings.checkin_time = settings.daily_time = settings.weekly_time = settings.weight_time = None
            flow = await dialogue.workflow(db, user.id, True)
            flow.started_at = flow.started_at or service.now_utc()
            body = "Напоминания отключены. Учёт сохранён."
        elif payload.kind == "eligibility":
            settings.nutrition_auto_eligible = payload.confirmed
            body = "Условия авторасчёта подтверждены. Можно попросить рассчитать КБЖУ." if payload.confirmed else "Авторасчёт отключён. Ручные КБЖУ доступны."
        else:
            try:
                settings.timezone = normalize_timezone(payload.value)
            except ValueError as error:
                raise HTTPException(422, "Укажите IANA-пояс, например Europe/Moscow или Asia/Yekaterinburg") from error
            body = f"Часовой пояс: {settings.timezone}. Подтверждённое расписание курса сохраняет прежние моменты приёмов."
        await service.apply_action(db, user.id, Action(kind="settings", settings=settings,
            expected_version=profile.version, request_key=payload.request_key))
    await db.commit()
    return {"text": body}


@telegram_ai_router.post("/mentor/reminders")
async def reminders(payload: Reminders, db: AsyncSession = Depends(get_db)):
    user = await owned_user(db, payload.telegram_user_id)
    await active_profile(db, user)
    # Expired reminders are not replayed after a long outage.
    from src.app.services.ai.companion.jobs import reminder_text
    profile = await service.profile_for(db, user.id)
    rows = (await db.execute(select(AIMessage, AICompanionReminder).join(AICompanionReminder, AICompanionReminder.message_id == AIMessage.id)
        .where(AIMessage.user_id == user.id, AIMessage.id > payload.after_id,
               AICompanionReminder.status != "cancelled",
               AICompanionReminder.due_at >= service.now_utc() - timedelta(minutes=30))
        .order_by(AIMessage.id).limit(20))).all()
    messages = []
    for message, reminder in rows:
        if await reminder_text(db, reminder, profile):
            messages.append({"message_id": message.id, "text": message.text})
    return {"messages": messages}
