import getpass
import logging
import os
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from config import (
    TELEGRAM_COMMUNITY_CHAT_ID,
    TELEGRAM_USERBOT_API_HASH,
    TELEGRAM_USERBOT_API_ID,
    TELEGRAM_USERBOT_ENABLED,
    TELEGRAM_USERBOT_PHONE,
    TELEGRAM_USERBOT_PROXY_URL,
    TELEGRAM_USERBOT_SESSION_PATH,
)
from src.app.services.community_topics import (
    TelegramForumTopicSnapshot,
    TelegramTopicSyncResult,
    reconcile_telegram_forum_topics,
)
from src.database import get_session


log = logging.getLogger(__name__)


class TelegramUserbotConfigurationError(RuntimeError):
    pass


class TelegramUserbotAuthorizationError(RuntimeError):
    pass


def _session_file_path() -> Path:
    value = Path(TELEGRAM_USERBOT_SESSION_PATH)
    if value.suffix != ".session":
        value = Path(f"{value}.session")
    return value


def _ensure_session_directory() -> None:
    session_file = _session_file_path()
    session_file.parent.mkdir(parents=True, exist_ok=True)
    with suppress(OSError):
        os.chmod(session_file.parent, 0o700)


def _lock_down_session_file() -> None:
    with suppress(OSError):
        os.chmod(_session_file_path(), 0o600)


def _telethon_proxy() -> tuple[Any, ...] | None:
    raw = (TELEGRAM_USERBOT_PROXY_URL or "").strip()
    if not raw:
        return None
    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "socks4", "socks5"} or not parsed.hostname:
        raise TelegramUserbotConfigurationError("TELEGRAM_USERBOT_PROXY_URL must be an HTTP, SOCKS4, or SOCKS5 URL")
    default_port = 8080 if scheme == "http" else 1080
    return (
        scheme,
        parsed.hostname,
        int(parsed.port or default_port),
        True,
        unquote(parsed.username) if parsed.username else None,
        unquote(parsed.password) if parsed.password else None,
    )


def _validate_configuration() -> None:
    if not TELEGRAM_USERBOT_API_ID or not TELEGRAM_USERBOT_API_HASH:
        raise TelegramUserbotConfigurationError(
            "TELEGRAM_USERBOT_API_ID and TELEGRAM_USERBOT_API_HASH are required"
        )
    if not TELEGRAM_COMMUNITY_CHAT_ID:
        raise TelegramUserbotConfigurationError("TELEGRAM_COMMUNITY_CHAT_ID is required")


def _build_client(*, receive_updates: bool = False):
    from telethon import TelegramClient

    _validate_configuration()
    _ensure_session_directory()
    return TelegramClient(
        str(TELEGRAM_USERBOT_SESSION_PATH),
        TELEGRAM_USERBOT_API_ID,
        str(TELEGRAM_USERBOT_API_HASH),
        proxy=_telethon_proxy(),
        receive_updates=receive_updates,
        request_retries=3,
        connection_retries=3,
        timeout=15,
        app_version="Elixir Community Bridge",
    )


async def _resolve_forum_peer(client: Any) -> Any:
    try:
        return await client.get_input_entity(TELEGRAM_COMMUNITY_CHAT_ID)
    except ValueError:
        async for dialog in client.iter_dialogs():
            if int(dialog.id) == int(TELEGRAM_COMMUNITY_CHAT_ID):
                return dialog.input_entity
    raise TelegramUserbotConfigurationError(
        "The Telethon user is not a member of the configured community supergroup"
    )


def _topic_snapshot(topic: Any, *, get_peer_id: Any) -> TelegramForumTopicSnapshot | None:
    thread_id = int(getattr(topic, "id", 0) or 0)
    title = str(getattr(topic, "title", "") or "").strip()
    if thread_id <= 0 or not title:
        return None
    creator = getattr(topic, "from_id", None)
    creator_peer_id = int(get_peer_id(creator)) if creator is not None else None
    icon_emoji_id = getattr(topic, "icon_emoji_id", None)
    return TelegramForumTopicSnapshot(
        thread_id=thread_id,
        name=title,
        icon_color=int(getattr(topic, "icon_color", 0) or 0) or None,
        icon_custom_emoji_id=str(icon_emoji_id) if icon_emoji_id is not None else None,
        is_closed=bool(getattr(topic, "closed", False)),
        is_hidden=bool(getattr(topic, "hidden", False)),
        is_pinned=bool(getattr(topic, "pinned", False)),
        top_message_id=int(getattr(topic, "top_message", 0) or 0) or None,
        creator_peer_id=creator_peer_id,
        created_at=getattr(topic, "date", None),
    )


async def fetch_telegram_forum_topics() -> list[TelegramForumTopicSnapshot]:
    """Fetch a complete authoritative topic list through a user MTProto session."""
    from telethon import functions, utils

    client = _build_client()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise TelegramUserbotAuthorizationError(
                "Telethon session is not authorized; run the telegram_userbot_login script"
            )
        me = await client.get_me()
        if bool(getattr(me, "bot", False)):
            raise TelegramUserbotAuthorizationError(
                "Telethon topic sync requires a user session, not a bot-token session"
            )
        peer = await _resolve_forum_peer(client)
        request_class = functions.messages.GetForumTopicsRequest
        offset_date = None
        offset_id = 0
        offset_topic = 0
        total_count: int | None = None
        snapshots_by_id: dict[int, TelegramForumTopicSnapshot] = {}

        while True:
            result = await client(
                request_class(
                    peer=peer,
                    offset_date=offset_date,
                    offset_id=offset_id,
                    offset_topic=offset_topic,
                    limit=100,
                    q=None,
                )
            )
            topics = list(getattr(result, "topics", None) or [])
            total_count = int(getattr(result, "count", len(topics)) or len(topics))
            if not topics:
                break

            page_new_ids = 0
            for topic in topics:
                snapshot = _topic_snapshot(topic, get_peer_id=utils.get_peer_id)
                if snapshot is None:
                    continue
                if snapshot.thread_id not in snapshots_by_id:
                    page_new_ids += 1
                snapshots_by_id[snapshot.thread_id] = snapshot

            if total_count and len(snapshots_by_id) >= total_count:
                break
            if page_new_ids == 0:
                break

            last_topic = topics[-1]
            offset_topic = int(getattr(last_topic, "id", 0) or 0)
            offset_id = int(getattr(last_topic, "top_message", 0) or 0)
            message_dates = {
                int(getattr(message, "id", 0) or 0): getattr(message, "date", None)
                for message in (getattr(result, "messages", None) or [])
            }
            offset_date = message_dates.get(offset_id) or getattr(last_topic, "date", None)

        if not snapshots_by_id:
            raise RuntimeError("Telegram returned no forum topics; refusing an empty reconciliation")
        if total_count is not None and len(snapshots_by_id) < total_count:
            raise RuntimeError(
                f"Telegram topic pagination was incomplete ({len(snapshots_by_id)}/{total_count})"
            )
        return list(snapshots_by_id.values())
    finally:
        await client.disconnect()
        _lock_down_session_file()


async def sync_telegram_forum_topics() -> TelegramTopicSyncResult:
    if not TELEGRAM_USERBOT_ENABLED:
        raise TelegramUserbotConfigurationError("Telegram userbot topic sync is disabled")
    snapshots = await fetch_telegram_forum_topics()
    async with get_session() as session:
        return await reconcile_telegram_forum_topics(
            session,
            chat_id=TELEGRAM_COMMUNITY_CHAT_ID,
            snapshots=snapshots,
        )


async def authorize_telegram_userbot() -> int:
    """Interactively authorize the configured user and persist its session."""
    client = _build_client()
    phone = TELEGRAM_USERBOT_PHONE or (lambda: input("Telegram phone number: ").strip())
    await client.start(
        phone=phone,
        code_callback=lambda: input("Telegram login code: ").strip(),
        password=lambda: getpass.getpass("Telegram 2FA password: "),
    )
    try:
        me = await client.get_me()
        if me is None or bool(getattr(me, "bot", False)):
            raise TelegramUserbotAuthorizationError("A real Telegram user account is required")
        return int(me.id)
    finally:
        await client.disconnect()
        _lock_down_session_file()
