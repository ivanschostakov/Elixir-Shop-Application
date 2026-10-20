import asyncio
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from config import TELEGRAM_COMMUNITY_CHAT_ID, TELEGRAM_USERBOT_ADMIN_LOG_SYNC_INTERVAL_SECONDS, ufa_now
from src.app.services.community import mark_community_telegram_messages_deleted
from src.database import get_session
from src.database.models import CommunityMessage, CommunityTelegramPart
from .common import log
from .authors import _telethon_message_text


def _admin_log_message(event: Any) -> tuple[str | None, Any | None]:
    if bool(getattr(event, "deleted_message", False)): return "delete", getattr(event, "old", None)
    if bool(getattr(event, "changed_message", False)): return "edit", getattr(event, "new", None)
    return None, None


async def _reconcile_telegram_admin_log(client: Any, peer: Any, *, min_event_id: int,) -> dict[str, int]:
    events = list(await client.get_admin_log(peer, limit=100, min_id=max(int(min_event_id), 0), edit=True, delete=True,))
    if not events: return {"cursor": min_event_id, "edited": 0, "deleted": 0}

    cursor = max(int(getattr(event, "id", 0) or 0) for event in events)
    deleted_ids: list[int] = []
    edited_messages: list[Any] = []
    for event in sorted(events, key=lambda item: int(getattr(item, "id", 0) or 0)):
        action, message = _admin_log_message(event)
        telegram_message_id = int(getattr(message, "id", 0) or 0)
        if telegram_message_id <= 0: continue
        if action == "delete": deleted_ids.append(telegram_message_id)
        elif action == "edit": edited_messages.append(message)

    edited = 0
    deleted = 0
    async with get_session() as db:
        if deleted_ids: deleted = await mark_community_telegram_messages_deleted(db, deleted_ids)
        for telegram_message in edited_messages:
            telegram_message_id = int(getattr(telegram_message, "id", 0) or 0)
            part = (await db.execute(select(CommunityTelegramPart).where(CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTelegramPart.telegram_message_id == telegram_message_id,).options(selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.topic),))).scalar_one_or_none()
            if part is None: continue
            logical = part.message
            new_text = _telethon_message_text(telegram_message, logical)
            edit_date = getattr(telegram_message, "edit_date", None) or ufa_now()
            changed = (logical.text != new_text or logical.deleted_at is not None or part.deleted_at is not None or logical.edited_at is None or edit_date > logical.edited_at)
            if not changed: continue
            logical.text = new_text
            logical.edited_at = edit_date
            logical.deleted_at = None
            part.deleted_at = None
            edited += 1
        await db.commit()
    return {"cursor": cursor, "edited": edited, "deleted": deleted}


async def _run_telegram_admin_log_reconciler(client: Any, peer: Any, stop_event: asyncio.Event) -> None:
    cursor = 0
    interval = max(float(TELEGRAM_USERBOT_ADMIN_LOG_SYNC_INTERVAL_SECONDS), 2.0)
    while not stop_event.is_set() and client.is_connected():
        try:
            result = await _reconcile_telegram_admin_log(client, peer, min_event_id=cursor)
            cursor = max(cursor, result["cursor"])
            if result["edited"] or result["deleted"]:
                log.info(
                    "telethon admin log reconciled edited=%s deleted=%s cursor=%s",
                    result["edited"],
                    result["deleted"],
                    cursor,
                )
        except asyncio.CancelledError: raise
        except Exception: log.exception("telethon admin log reconciliation failed")
        try: await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            pass
