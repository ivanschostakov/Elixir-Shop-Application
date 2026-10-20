from typing import Any
from config import TELEGRAM_COMMUNITY_CHAT_ID, TELEGRAM_USERBOT_ENABLED
from src.app.services.community_topics import TelegramForumTopicSnapshot, TelegramTopicSyncResult, reconcile_telegram_forum_topics
from src.database import get_session
from .session import TelegramUserbotConfigurationError, _build_client, _lock_down_session_file, _require_authorized_user, _resolve_forum_peer


def _topic_snapshot(topic: Any, *, get_peer_id: Any) -> TelegramForumTopicSnapshot | None:
    thread_id = int(getattr(topic, "id", 0) or 0)
    title = str(getattr(topic, "title", "") or "").strip()
    if thread_id <= 0 or not title: return None
    creator = getattr(topic, "from_id", None)
    creator_peer_id = int(get_peer_id(creator)) if creator is not None else None
    icon_emoji_id = getattr(topic, "icon_emoji_id", None)
    return TelegramForumTopicSnapshot(thread_id=thread_id, name=title, icon_color=int(getattr(topic, "icon_color", 0) or 0) or None, icon_custom_emoji_id=str(icon_emoji_id) if icon_emoji_id is not None else None, is_closed=bool(getattr(topic, "closed", False)), is_hidden=bool(getattr(topic, "hidden", False)), is_pinned=bool(getattr(topic, "pinned", False)), top_message_id=int(getattr(topic, "top_message", 0) or 0) or None, creator_peer_id=creator_peer_id, created_at=getattr(topic, "date", None),)


async def _fetch_telegram_forum_topics_with_client(client: Any) -> list[TelegramForumTopicSnapshot]:
    from telethon import functions, utils

    await _require_authorized_user(client)
    peer = await _resolve_forum_peer(client)
    request_class = functions.messages.GetForumTopicsRequest
    offset_date = None
    offset_id = 0
    offset_topic = 0
    total_count: int | None = None
    snapshots_by_id: dict[int, TelegramForumTopicSnapshot] = {}

    while True:
        result = await client(request_class(peer=peer, offset_date=offset_date, offset_id=offset_id, offset_topic=offset_topic, limit=100, q=None,))
        topics = list(getattr(result, "topics", None) or [])
        total_count = int(getattr(result, "count", len(topics)) or len(topics))
        if not topics: break

        page_new_ids = 0
        for topic in topics:
            snapshot = _topic_snapshot(topic, get_peer_id=utils.get_peer_id)
            if snapshot is None: continue
            if snapshot.thread_id not in snapshots_by_id: page_new_ids += 1
            snapshots_by_id[snapshot.thread_id] = snapshot

        if total_count and len(snapshots_by_id) >= total_count: break
        if page_new_ids == 0: break

        last_topic = topics[-1]
        offset_topic = int(getattr(last_topic, "id", 0) or 0)
        offset_id = int(getattr(last_topic, "top_message", 0) or 0)
        message_dates = {int(getattr(message, "id", 0) or 0): getattr(message, "date", None) for message in (getattr(result, "messages", None) or [])}
        offset_date = message_dates.get(offset_id) or getattr(last_topic, "date", None)

    if not snapshots_by_id: raise RuntimeError("Telegram returned no forum topics; refusing an empty reconciliation")
    if total_count is not None and len(snapshots_by_id) < total_count: raise RuntimeError(f"Telegram topic pagination was incomplete ({len(snapshots_by_id)}/{total_count})")
    return list(snapshots_by_id.values())


async def fetch_telegram_forum_topics() -> list[TelegramForumTopicSnapshot]:
    """Fetch a complete authoritative topic list through a user MTProto session."""
    client = _build_client()
    await client.connect()
    try: return await _fetch_telegram_forum_topics_with_client(client)
    finally:
        await client.disconnect()
        _lock_down_session_file()


async def _sync_telegram_forum_topics_with_client(client: Any) -> TelegramTopicSyncResult:
    snapshots = await _fetch_telegram_forum_topics_with_client(client)
    async with get_session() as session:
        return await reconcile_telegram_forum_topics(session, chat_id=TELEGRAM_COMMUNITY_CHAT_ID, snapshots=snapshots,)


async def sync_telegram_forum_topics() -> TelegramTopicSyncResult:
    if not TELEGRAM_USERBOT_ENABLED: raise TelegramUserbotConfigurationError("Telegram userbot topic sync is disabled")
    snapshots = await fetch_telegram_forum_topics()
    async with get_session() as session:
        return await reconcile_telegram_forum_topics(session, chat_id=TELEGRAM_COMMUNITY_CHAT_ID, snapshots=snapshots,)
