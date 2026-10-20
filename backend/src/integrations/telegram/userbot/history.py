from datetime import timedelta
from typing import Any
from sqlalchemy import select
from config import TELEGRAM_COMMUNITY_CHAT_ID, TELEGRAM_USERBOT_ENABLED, TELEGRAM_USERBOT_FULL_HISTORY_RECONCILE_SECONDS, ufa_now
from src.app.services.community import _refresh_topic_last_message, mark_community_telegram_messages_deleted
from src.database import get_session
from src.database.models import CommunityMessage, CommunityTelegramPart, CommunityTopic
from .session import TelegramUserbotConfigurationError, _build_client, _lock_down_session_file, _require_authorized_user, _resolve_forum_peer
from .messages import _upsert_telethon_message


async def _sync_telegram_forum_history_with_client(client: Any) -> dict[str, int]:
    peer = await _resolve_forum_peer(client)
    now = ufa_now()
    full_cutoff = now - timedelta(seconds=max(TELEGRAM_USERBOT_FULL_HISTORY_RECONCILE_SECONDS, 3600))
    imported = 0
    updated = 0
    deleted = 0
    scanned = 0
    async with get_session() as db:
        topics = list((await db.execute(select(CommunityTopic).where(CommunityTopic.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTopic.is_deleted.is_(False),).order_by(CommunityTopic.telegram_thread_id.asc()))).scalars().all())
        for topic in topics:
            if int(topic.telegram_thread_id) <= 0: continue
            initial_backfill = not topic.telegram_history_complete
            # An unfinished first pass can safely resume from its last committed
            # message. There is no older authoritative snapshot to reconcile for
            # deletions yet; the first scheduled full pass handles that after the
            # archive is complete. This keeps deploys/reconnects from repeatedly
            # rescanning a large topic from message zero.
            full_reconcile = (not initial_backfill and (topic.telegram_history_synced_at is None or topic.telegram_history_synced_at < full_cutoff))
            min_id = 0 if full_reconcile else int(topic.telegram_history_max_message_id or 0)
            seen_ids: set[int] = set()
            async for telegram_message in client.iter_messages(
                peer,
                reply_to=topic.telegram_thread_id,
                min_id=min_id,
                reverse=True,
            ):
                telegram_message_id = int(getattr(telegram_message, "id", 0) or 0)
                if telegram_message_id <= 0: continue
                seen_ids.add(telegram_message_id)
                scanned += 1
                existing = (await db.execute(select(CommunityTelegramPart.id).where(CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTelegramPart.telegram_message_id == telegram_message_id,))).scalar_one_or_none()
                _, changed = await _upsert_telethon_message(db, client=client, topic=topic, telegram_message=telegram_message,)
                if changed:
                    if existing: updated += 1
                    else: imported += 1
                topic.telegram_history_min_message_id = min(topic.telegram_history_min_message_id or telegram_message_id, telegram_message_id,)
                topic.telegram_history_max_message_id = max(topic.telegram_history_max_message_id or telegram_message_id, telegram_message_id,)
                if scanned % 100 == 0: await db.commit()

            if full_reconcile:
                stored_ids = set((await db.execute(select(CommunityTelegramPart.telegram_message_id).join(CommunityMessage, CommunityMessage.id == CommunityTelegramPart.message_id).where(CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityMessage.topic_id == topic.id, CommunityTelegramPart.deleted_at.is_(None), CommunityTelegramPart.created_at <= now,))).scalars().all())
                missing_ids = sorted(stored_ids - seen_ids)
                if missing_ids: deleted += await mark_community_telegram_messages_deleted(db, missing_ids, deleted_at=now)
            topic.telegram_history_complete = True
            topic.telegram_history_synced_at = now
            await _refresh_topic_last_message(db, topic)
            await db.commit()
    return {"scanned": scanned, "imported": imported, "updated": updated, "deleted": deleted}


async def sync_telegram_forum_history() -> dict[str, int]:
    if not TELEGRAM_USERBOT_ENABLED: raise TelegramUserbotConfigurationError("Telegram userbot history sync is disabled")
    client = _build_client()
    await client.connect()
    try:
        await _require_authorized_user(client)
        return await _sync_telegram_forum_history_with_client(client)
    finally:
        await client.disconnect()
        _lock_down_session_file()
