"""Durable reminders and erasure queue, run by the existing notification worker."""
import logging
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import or_, select

import config
from src.database import get_session
from src.database.models import AIChat, AIMessage, User, UserPushToken
from src.database.models.ai.companion import AICompanionEntry, AICompanionEvent, AICompanionProfile, AICompanionReminder, AIProviderResource
from src.integrations.ai.enums import MessageSender
from . import service
from .schemas import Settings
from .timezones import timezone_info

log = logging.getLogger(__name__)


def local_due(day, value, zone):
    local = datetime.combine(day, value, zone)
    utc = local.astimezone(timezone.utc)
    # Never send twice on the autumn clock change; skip nonexistent spring times.
    return utc if utc.astimezone(zone).replace(tzinfo=None) == local.replace(tzinfo=None) else None


async def schedule_recurring(db, profile, now):
    settings = Settings.model_validate(profile.settings)
    zone = timezone_info(settings.timezone)
    today = now.astimezone(zone).date()
    kinds = [("daily", settings.daily_time), ("weight", settings.weight_time)]
    if config.AI_COMPANION_DIALOGUE_ENABLED and settings.daily_time is None and settings.checkin_topics:
        kinds.append(("checkin", settings.checkin_time))
    if today.weekday() == settings.weekly_day:
        kinds.append(("weekly", settings.weekly_time))
    if settings.supply_reminders:
        kinds.append(("supply", time(12)))
    for kind, value in kinds:
        if value is None:
            continue
        due = local_due(today, value, zone)
        if due is None or due < profile.created_at:
            continue
        key = f"{kind}:{today.isoformat()}"
        exists = (await db.execute(select(AICompanionReminder).where(AICompanionReminder.user_id == profile.user_id, AICompanionReminder.dedupe_key == key))).scalar_one_or_none()
        if exists is None:
            db.add(AICompanionReminder(user_id=profile.user_id, kind=kind, dedupe_key=key, due_at=due))
        elif exists.status == "cancelled" and exists.message_id is None and exists.attempts == 0 and due >= now:
            # Reuse an unsent local-day slot after timezone/settings changes.
            # Sent/attempted messages are never replayed on a clock change.
            exists.status, exists.due_at, exists.next_attempt_at = "pending", due, None


async def reminder_text(db, row, profile):
    settings = Settings.model_validate(profile.settings)
    if row.kind == "checkin":
        if not config.AI_COMPANION_DIALOGUE_ENABLED or settings.checkin_time is None or settings.daily_time is not None or not settings.checkin_topics:
            return None
        zone = timezone_info(settings.timezone)
        start = row.due_at.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
        summary = await service.summary_for(db, row.user_id, start, row.due_at)
        entries = await service.entries_for(db, row.user_id, start, row.due_at)
        kinds = {entry.kind for entry in entries}
        tracked = set((await db.execute(select(AICompanionEntry.kind).where(AICompanionEntry.user_id == row.user_id).distinct())).scalars())
        nutrition_goal = profile.data.get("goal") in {"weight_loss", "maintain"}
        questions = []
        topics = settings.checkin_topics
        if "course" in topics and summary["events"]["pending"]:
            questions.append("В расписании есть события без отметки. Что удалось выполнить, а что пропустили?")
        if "nutrition" in topics and (nutrition_goal or "meal" in tracked) and not summary["meals_logged"]:
            questions.append("Что сегодня ели? Можно описать или прислать фото.")
        if "weight" in topics and (nutrition_goal or "weight" in tracked) and "weight" not in kinds:
            questions.append("Если сегодня измеряли вес, напишите результат.")
        if "wellbeing" in topics and "wellbeing" not in kinds:
            questions.append("Как самочувствие сегодня?")
        if questions:
            return "Давайте коротко подведём итоги дня.\n" + "\n".join(questions[:2]) + "\nОтвечайте здесь, в чате. Время и темы можно изменить сообщением; «не напоминай» отключит уведомления."
        return f"Спасибо за записи. Сегодня внесено приёмов пищи: {summary['meals_logged']}, измерений веса: {summary['weight_measurements']}. " + summary["coverage_note"]
    if row.kind == "course":
        plan = await service.current_plan(db, row.user_id)
        event = await db.get(AICompanionEvent, row.event_id)
        if not settings.course_reminders or not plan or plan.status != "active" or not event or event.plan_id != plan.id or event.status != "pending":
            return None
        return f"В вашем подтверждённом расписании есть событие: {event.data['name']}. Если уже выполнили или пропустили, напишите об этом здесь. Это напоминание о вашем расписании, не новое назначение."
    if row.kind == "weight":
        return "Если измеряли вес, напишите результат здесь — помогу внести в дневник." if settings.weight_time else None
    if row.kind == "supply":
        if not settings.supply_reminders:
            return None
        result = await service.supply_for(db, row.user_id, settings.supply_days)
        if not any(item.get("available") and item.get("packages", 0) > 0 for item in result.get("items", [])):
            return None
        if config.AI_COMPANION_DIALOGUE_ENABLED:
            return "По подтверждённому плану и внесённому остатку запаса может не хватить на выбранный период. Напишите здесь фактический остаток — помогу сверить учёт."
        return "По подтверждённому плану и внесённому остатку запаса может не хватить на выбранный период. Проверьте фактический остаток в разделе «Запас»."
    if row.kind == "daily" and not settings.daily_time or row.kind == "weekly" and not settings.weekly_time:
        return None
    zone = timezone_info(settings.timezone)
    midnight = row.due_at.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    start = midnight - timedelta(days=7) if row.kind == "weekly" else midnight
    end = midnight if row.kind == "weekly" else row.due_at
    summary = await service.summary_for(db, row.user_id, start.astimezone(timezone.utc), end.astimezone(timezone.utc))
    label = "Итоги предыдущих 7 дней" if row.kind == "weekly" else "Итоги дня на сейчас"
    text = f"{label}: записей еды — {summary['meals_logged']}, всего {summary['nutrition']['kcal']} ккал. Отмечено событий: выполнено — {summary['events']['done']}, пропущено — {summary['events']['skipped']}, без отметки — {summary['events']['pending']}."
    if summary["weight_change_kg"] is not None:
        text += f" Изменение между внесёнными измерениями веса: {summary['weight_change_kg']} кг."
    return text + " " + summary["coverage_note"]


async def deliver_reminder(db, row, profile, now):
    from src.app.services.push_notifications import _build_push_messages, _send_expo_push_messages, _delete_invalid_push_tokens
    body = await reminder_text(db, row, profile)
    # Do not send an overdue injection reminder after a long worker outage.
    grace = timedelta(minutes=30) if row.kind == "course" else timedelta(hours=1) if row.kind == "checkin" else timedelta(hours=12)
    if not body or now - row.due_at > grace:
        row.status = "cancelled"
        return
    if row.message_id is None:
        chat = (await db.execute(select(AIChat).where(AIChat.user_id == row.user_id))).scalar_one_or_none()
        if chat is None:
            chat = AIChat(user_id=row.user_id, conversation_id=f"reset:{uuid4()}", current_tokens=0, total_tokens=0)
            db.add(chat)
            await db.flush()
        message = AIMessage(user_id=row.user_id, chat_id=chat.id, text=body, sender=MessageSender.AI, is_sensitive=True, context_json={"reminder_id": row.id, "event_id": row.event_id})
        db.add(message)
        await db.flush()
        row.message_id = message.id
    data = {"type": "ai_companion_supply" if row.kind == "supply" else "ai_companion", "reminder_id": row.id, "message_id": row.message_id, "event_id": row.event_id}
    tokens = list((await db.execute(select(UserPushToken).where(UserPushToken.user_id == row.user_id, UserPushToken.platform.in_(["ios", "android"])))).scalars().all())
    messages = _build_push_messages(tokens, title="Elixir", body="Есть обновление в вашем чате.", data=data)
    row.attempts += 1
    if not messages:
        row.status = "sent"  # In-chat delivery still works without a push permission/token.
        return
    result = await _send_expo_push_messages(messages)
    await _delete_invalid_push_tokens(db, push_tokens=tokens, invalid_tokens=set(result.invalid_tokens), commit=False)
    if result.accepted_tokens or not (result.failed_tokens - result.invalid_tokens):
        row.status = "sent"
    elif row.attempts >= 5:
        row.status = "failed"
    else:
        row.next_attempt_at = now + timedelta(minutes=2 ** row.attempts)


async def process_reminders():
    if not config.AI_COMPANION_ENABLED:
        return
    # Iterate all profiles, locking in the same order as manual changes/erasure.
    last_id = 0
    while True:
        async with get_session() as db:
            profiles = list((await db.execute(select(AICompanionProfile.id, AICompanionProfile.user_id).where(AICompanionProfile.enabled.is_(True), AICompanionProfile.id > last_id).order_by(AICompanionProfile.id).limit(100))).all())
        if not profiles:
            return
        for profile_id, user_id in profiles:
            last_id = profile_id
            async with get_session() as db:
                locked = (await db.execute(select(User.id).where(User.id == user_id, User.is_active.is_(True)).with_for_update(skip_locked=True))).scalar_one_or_none()
                if locked is None:
                    continue
                profile = await service.profile_for(db, user_id)
                if not profile or not profile.enabled:
                    continue
                try:
                    await service.require_consent(db, user_id)
                except Exception:
                    continue
                now = service.now_utc()
                await schedule_recurring(db, profile, now)
                await db.flush()
                rows = list((await db.execute(select(AICompanionReminder).where(AICompanionReminder.user_id == user_id, AICompanionReminder.status == "pending", AICompanionReminder.due_at <= now, or_(AICompanionReminder.next_attempt_at.is_(None), AICompanionReminder.next_attempt_at <= now)).order_by(AICompanionReminder.due_at).limit(20))).scalars().all())
                for row in rows:
                    previous_attempts = row.attempts
                    try:
                        await deliver_reminder(db, row, profile, now)
                    except Exception:
                        # Persist retry state without logging medical content or push tokens.
                        row.attempts = previous_attempts + 1
                        row.status = "failed" if row.attempts >= 5 else "pending"
                        row.next_attempt_at = now + timedelta(minutes=2 ** min(row.attempts, 5))
                        log.warning("Companion reminder failed id=%s", row.id)
                await db.commit()


async def delete_provider_resource(client, kind, external_id):
    if kind == "local_file":
        root = (config.PRIVATE_MEDIA_DIR / "ai_companion").resolve()
        path = (root / external_id).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError("Invalid private attachment path")
        path.unlink(missing_ok=True)
    elif kind == "file":
        await client.files.delete(external_id)
    elif kind == "response":
        await client.responses.delete(external_id)
    elif kind == "conversation":
        # OpenAI conversation deletion alone does NOT erase the stored items.
        while True:
            page = await client.conversations.items.list(external_id, limit=100)
            if not page.data:
                break
            for item in page.data:
                try:
                    await client.conversations.items.delete(item.id, conversation_id=external_id)
                except Exception as error:
                    if getattr(error, "status_code", None) != 404:
                        raise
        await client.conversations.delete(external_id)
    else:
        raise ValueError("Unknown resource type")


async def process_erasure(client=None):
    from openai import AsyncOpenAI
    import httpx
    own_client = client is None
    if own_client:
        client = AsyncOpenAI(api_key=config.OPENAI_API_KEY, timeout=30, max_retries=0, http_client=httpx.AsyncClient(proxy=config.OPENAI_PROXY_URL) if config.OPENAI_PROXY_URL else None)
    try:
        for _ in range(50):
            async with get_session() as db:
                now = service.now_utc()
                row = (await db.execute(select(AIProviderResource).where(AIProviderResource.status == "pending_delete", or_(AIProviderResource.next_attempt_at.is_(None), AIProviderResource.next_attempt_at <= now)).order_by(AIProviderResource.id).with_for_update(skip_locked=True).limit(1))).scalar_one_or_none()
                if row is None:
                    return
                try:
                    await delete_provider_resource(client, row.kind, row.external_id)
                    row.status = "deleted"
                except Exception as error:
                    if getattr(error, "status_code", None) == 404:
                        row.status = "deleted"
                    else:
                        row.attempts += 1
                        row.next_attempt_at = now + timedelta(minutes=min(1440, 2 ** min(row.attempts, 11)))
                        log.warning("Companion erasure will retry resource_id=%s attempt=%s", row.id, row.attempts)
                await db.commit()
    finally:
        if own_client:
            await client.close()


async def run_once():
    await process_erasure()
    await process_reminders()
