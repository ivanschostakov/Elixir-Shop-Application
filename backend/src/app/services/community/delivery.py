import asyncio
from datetime import timedelta
from typing import Any
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from config import TELEGRAM_COMMUNITY_CHAT_ID, TELEGRAM_COMMUNITY_ENABLED, ufa_now
from src.database.models import CommunityMessage, CommunityReaction, CommunityTelegramPart, User
from src.integrations.telegram import TelegramBotAPIError, TelegramBotClient, get_telegram_bot_client
from .common import COMMUNITY_ATTACHMENTS_DIR
from .telegram_helpers import _reply_parameters, _telegram_app_header, _telegram_app_reaction_notification, _telegram_author_entities, _telegram_bot_thread_id, _telegram_retry_delay_seconds, _telegram_text_chunks


async def recover_stale_community_deliveries(db: AsyncSession, *, older_than_seconds: int = 300) -> int:
    if not TELEGRAM_COMMUNITY_ENABLED or not TELEGRAM_COMMUNITY_CHAT_ID: return 0
    cutoff = ufa_now() - timedelta(seconds=max(older_than_seconds, 60))
    stale_result = await db.execute(update(CommunityMessage).where(CommunityMessage.source == "app", CommunityMessage.delivery_status == "sending", CommunityMessage.updated_at < cutoff,).values(delivery_status="delivery_unknown", delivery_error="Delivery was interrupted; check Telegram before retrying.",))
    retryable_result = await db.execute(update(CommunityMessage).where(CommunityMessage.source == "app", CommunityMessage.delivery_status == "failed", CommunityMessage.delivery_error.like("Telegram % request failed"),).values(delivery_status="queued", delivery_error=None, next_delivery_attempt_at=None,))
    await db.commit()
    return int(stale_result.rowcount or 0) + int(retryable_result.rowcount or 0)


async def relay_next_community_message(db: AsyncSession, *, telegram_client: TelegramBotClient | None = None) -> bool:
    if not TELEGRAM_COMMUNITY_ENABLED or not TELEGRAM_COMMUNITY_CHAT_ID: return False
    now = ufa_now()
    stmt = select(CommunityMessage).where(CommunityMessage.source == "app", CommunityMessage.deleted_at.is_(None), CommunityMessage.delivery_status == "queued", or_(CommunityMessage.next_delivery_attempt_at.is_(None), CommunityMessage.next_delivery_attempt_at <= now)).order_by(CommunityMessage.id.asc()).limit(1).options(selectinload(CommunityMessage.topic), selectinload(CommunityMessage.author), selectinload(CommunityMessage.attachments), selectinload(CommunityMessage.telegram_parts), selectinload(CommunityMessage.reply_to).selectinload(CommunityMessage.telegram_parts)).with_for_update(skip_locked=True)
    message = (await db.execute(stmt)).scalar_one_or_none()
    if message is None: return False
    if message.topic is None or message.topic.is_deleted:
        message.delivery_status = "failed"
        message.delivery_error = "The Telegram topic no longer exists."
        await db.commit()
        return True
    message.delivery_status = "sending"; message.delivery_attempts += 1; message.delivery_error = None
    await db.commit()
    client = telegram_client or get_telegram_bot_client()
    author_name, header = _telegram_app_header(message)
    text = f"{header}\n\n{message.text}" if message.text else header
    common: dict[str, Any] = {
        "chat_id": TELEGRAM_COMMUNITY_CHAT_ID,
        "message_thread_id": _telegram_bot_thread_id(message.topic),
        "reply_parameters": await _reply_parameters(message),
    }
    sent_results: list[dict[str, Any]] = []

    async def store_result(result: Any) -> None:
        if not isinstance(result, dict): return
        sent_results.append(result)
        telegram_message_id = int(result.get("message_id") or 0)
        if telegram_message_id:
            db.add(CommunityTelegramPart(message_id=message.id, telegram_chat_id=TELEGRAM_COMMUNITY_CHAT_ID, telegram_message_id=telegram_message_id))
            await db.commit()

    async def send_text_parts(value: str) -> None:
        for chunk in _telegram_text_chunks(value):
            if sent_results: await asyncio.sleep(3)
            result = await client.call("sendMessage", data={**common, "text": chunk, "entities": _telegram_author_entities(chunk, author_name)})
            await store_result(result)
            common["reply_parameters"] = None

    try:
        if not message.attachments: await send_text_parts(text)
        else:
            prefix_sent = False
            caption = text
            if len(caption) > 950:
                await send_text_parts(text)
                prefix_sent = True
            for index, attachment in enumerate(message.attachments):
                if sent_results: await asyncio.sleep(3)
                path = COMMUNITY_ATTACHMENTS_DIR / str(attachment.local_filename)
                method = "sendPhoto" if attachment.kind == "image" else "sendDocument"
                field = "photo" if attachment.kind == "image" else "document"
                rendered_caption = "" if prefix_sent or index else caption
                result = await client.call(method, data={**common, "caption": rendered_caption, "caption_entities": _telegram_author_entities(rendered_caption, author_name)}, files={field: (attachment.original_filename or attachment.filename, path.read_bytes(), attachment.mime_type or "application/octet-stream")}, timeout=60.0)
                if isinstance(result, dict): attachment.telegram_message_id = int(result.get("message_id") or 0) or None
                await store_result(result)
                common["reply_parameters"] = None
        message.delivery_status = "sent"; message.next_delivery_attempt_at = None
        await db.commit(); return True
    except TelegramBotAPIError as exc:
        if (exc.retryable or exc.retry_after) and not sent_results:
            retry_delay = _telegram_retry_delay_seconds(message.delivery_attempts, retry_after=exc.retry_after,)
            message.delivery_status = "queued"
            message.next_delivery_attempt_at = ufa_now() + timedelta(seconds=retry_delay)
        elif sent_results: message.delivery_status = "delivery_unknown"
        else: message.delivery_status = "failed"
        message.delivery_error = str(exc)[:1000]; await db.commit(); return True
    except (TimeoutError, OSError) as exc:
        message.delivery_status = "delivery_unknown"; message.delivery_error = str(exc)[:1000]
        await db.commit(); return True


async def relay_next_community_reaction(db: AsyncSession, *, telegram_client: TelegramBotClient | None = None,) -> bool:
    if not TELEGRAM_COMMUNITY_ENABLED or not TELEGRAM_COMMUNITY_CHAT_ID: return False
    now = ufa_now()
    stmt = (select(CommunityReaction).join(CommunityMessage, CommunityReaction.message_id == CommunityMessage.id).where(CommunityReaction.delivery_status == "queued", or_(CommunityReaction.next_delivery_attempt_at.is_(None), CommunityReaction.next_delivery_attempt_at <= now,), CommunityMessage.deleted_at.is_(None), CommunityMessage.telegram_parts.any(CommunityTelegramPart.deleted_at.is_(None)),).order_by(CommunityReaction.id.asc()).limit(1).options(selectinload(CommunityReaction.message).selectinload(CommunityMessage.topic), selectinload(CommunityReaction.message).selectinload(CommunityMessage.telegram_parts),).with_for_update(skip_locked=True))
    reaction = (await db.execute(stmt)).scalar_one_or_none()
    if reaction is None: return False
    message = reaction.message
    active_parts = [part for part in message.telegram_parts if part.deleted_at is None]
    user = await db.get(User, reaction.user_id)
    if user is None or message.topic is None or not active_parts:
        reaction.delivery_status = "failed"
        reaction.delivery_error = "The Telegram reaction target is unavailable."
        await db.commit()
        return True

    reaction.delivery_attempts += 1
    reaction.delivery_error = None
    client = telegram_client or get_telegram_bot_client()
    author_name, notification_text = _telegram_app_reaction_notification(user, reaction.emoji)
    try:
        result = await client.call(
            "sendMessage",
            data={
                "chat_id": TELEGRAM_COMMUNITY_CHAT_ID,
                "message_thread_id": _telegram_bot_thread_id(message.topic),
                "reply_parameters": {
                    "message_id": active_parts[0].telegram_message_id,
                    "allow_sending_without_reply": True,
                },
                "text": notification_text,
                "entities": _telegram_author_entities(notification_text, author_name),
            },
        )
        telegram_message_id = int(result.get("message_id") or 0) if isinstance(result, dict) else 0
        if telegram_message_id <= 0: raise TelegramBotAPIError("Telegram sendMessage returned an invalid response", retryable=True,)
        reaction.telegram_chat_id = TELEGRAM_COMMUNITY_CHAT_ID
        reaction.telegram_message_id = telegram_message_id
        reaction.delivery_status = "sent"
        reaction.next_delivery_attempt_at = None
        await db.commit()
        return True
    except TelegramBotAPIError as exc:
        if exc.retryable or exc.retry_after:
            retry_delay = _telegram_retry_delay_seconds(reaction.delivery_attempts, retry_after=exc.retry_after,)
            reaction.delivery_status = "queued"
            reaction.next_delivery_attempt_at = ufa_now() + timedelta(seconds=retry_delay)
        else: reaction.delivery_status = "failed"
        reaction.delivery_error = str(exc)[:1000]
        await db.commit()
        return True
    except (TimeoutError, OSError) as exc:
        reaction.delivery_status = "delivery_unknown"
        reaction.delivery_error = str(exc)[:1000]
        await db.commit()
        return True
