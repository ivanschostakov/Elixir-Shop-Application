import getpass
import asyncio
import hashlib
import logging
import os
from contextlib import suppress
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from config import (
    TELEGRAM_COMMUNITY_CHAT_ID,
    TELEGRAM_USERBOT_API_HASH,
    TELEGRAM_USERBOT_API_ID,
    TELEGRAM_USERBOT_ENABLED,
    TELEGRAM_USERBOT_FULL_HISTORY_RECONCILE_SECONDS,
    TELEGRAM_USERBOT_HISTORY_SYNC_INTERVAL_SECONDS,
    TELEGRAM_USERBOT_PHONE,
    TELEGRAM_USERBOT_PROXY_URL,
    TELEGRAM_USERBOT_SESSION_PATH,
    TELEGRAM_USERBOT_TOPIC_SYNC_INTERVAL_SECONDS,
    ufa_now,
)
from src.app.services.community import (
    COMMUNITY_ATTACHMENTS_DIR,
    _get_or_create_topic,
    _refresh_topic_last_message,
    _safe_filename,
    _upsert_author,
    mark_community_telegram_messages_deleted,
)
from src.app.services.community_topics import (
    TelegramForumTopicSnapshot,
    TelegramTopicSyncResult,
    reconcile_telegram_forum_topics,
)
from src.database import get_session
from src.database.crud.auth.user import get_user_by_telegram_user_id
from src.database.models import (
    CommunityAttachment,
    CommunityMessage,
    CommunityTelegramPart,
    CommunityTopic,
)


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


async def _require_authorized_user(client: Any) -> None:
    if not await client.is_user_authorized():
        raise TelegramUserbotAuthorizationError(
            "Telethon session is not authorized; run the telegram_userbot_login script"
        )
    me = await client.get_me()
    if bool(getattr(me, "bot", False)):
        raise TelegramUserbotAuthorizationError(
            "Telethon topic sync requires a user session, not a bot-token session"
        )


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


async def fetch_telegram_forum_topics() -> list[TelegramForumTopicSnapshot]:
    """Fetch a complete authoritative topic list through a user MTProto session."""
    client = _build_client()
    await client.connect()
    try:
        return await _fetch_telegram_forum_topics_with_client(client)
    finally:
        await client.disconnect()
        _lock_down_session_file()


async def _sync_telegram_forum_topics_with_client(client: Any) -> TelegramTopicSyncResult:
    snapshots = await _fetch_telegram_forum_topics_with_client(client)
    async with get_session() as session:
        return await reconcile_telegram_forum_topics(
            session,
            chat_id=TELEGRAM_COMMUNITY_CHAT_ID,
            snapshots=snapshots,
        )


def _telethon_author_snapshot(sender: Any, telegram_message_id: int) -> tuple[str, int, str]:
    from telethon import utils

    if sender is None:
        return "user", -telegram_message_id, "Telegram member"
    title = str(getattr(sender, "title", "") or "").strip()
    if title:
        return "chat", int(utils.get_peer_id(sender) or -telegram_message_id), title
    peer_id = int(utils.get_peer_id(sender) or -telegram_message_id)
    full_name = " ".join(
        str(getattr(sender, key, "") or "").strip()
        for key in ("first_name", "last_name")
    ).strip() or "Telegram member"
    return "user", peer_id, full_name


def _telethon_message_text(message: Any, logical: CommunityMessage | None = None) -> str:
    value = str(getattr(message, "message", "") or "")
    header, separator, body = value.partition("\n\n")
    if separator and (
        (logical is not None and logical.source == "app")
        or header.endswith(" · Elixir app")
    ):
        return body
    return value


def _archived_app_author_name(message: Any) -> str | None:
    header = str(getattr(message, "message", "") or "").partition("\n\n")[0]
    suffix = " · Elixir app"
    if not header.endswith(suffix):
        return None
    return header[: -len(suffix)].strip() or None


async def _store_telethon_attachment(
    db: Any,
    *,
    client: Any,
    telegram_message: Any,
    logical: CommunityMessage,
) -> None:
    telegram_message_id = int(getattr(telegram_message, "id", 0) or 0)
    is_photo = getattr(telegram_message, "photo", None) is not None
    unsupported_type = next(
        (
            key
            for key in ("voice", "video", "video_note", "sticker", "gif", "audio", "poll", "geo", "contact")
            if getattr(telegram_message, key, None) is not None
        ),
        None,
    )
    file_info = getattr(telegram_message, "file", None)
    is_document = getattr(telegram_message, "document", None) is not None and unsupported_type is None
    if not is_photo and not is_document:
        if unsupported_type:
            logical.unsupported_type = "location" if unsupported_type == "geo" else unsupported_type
        return

    size_bytes = int(getattr(file_info, "size", 0) or 0)
    fallback = f"photo-{telegram_message_id}.jpg" if is_photo else f"file-{telegram_message_id}"
    original = _safe_filename(getattr(file_info, "name", None), fallback)
    mime_type = str(getattr(file_info, "mime_type", "") or ("image/jpeg" if is_photo else "application/octet-stream"))
    attachment = CommunityAttachment(
        message_id=logical.id,
        kind="image" if is_photo else "document",
        original_filename=original,
        filename=f"telegram-{telegram_message_id}",
        mime_type=mime_type,
        size_bytes=size_bytes,
        telegram_message_id=telegram_message_id,
        status="telegram_only",
    )
    db.add(attachment)
    await db.flush()
    from config import TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES

    if not size_bytes or size_bytes > TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES:
        return
    local_filename = f"{logical.id}-{telegram_message_id}"
    target = COMMUNITY_ATTACHMENTS_DIR / local_filename
    try:
        downloaded = await client.download_media(telegram_message, file=str(target))
        if downloaded and target.exists():
            attachment.local_filename = local_filename
            attachment.size_bytes = target.stat().st_size
            attachment.status = "ready"
    except (OSError, TimeoutError):
        target.unlink(missing_ok=True)
        log.info("telethon history media download skipped message_id=%s", telegram_message_id)
    except Exception:
        target.unlink(missing_ok=True)
        log.exception("telethon history media download failed message_id=%s", telegram_message_id)


async def _upsert_telethon_message(
    db: Any,
    *,
    client: Any,
    topic: CommunityTopic,
    telegram_message: Any,
) -> tuple[CommunityMessage | None, bool]:
    telegram_message_id = int(getattr(telegram_message, "id", 0) or 0)
    if telegram_message_id <= 0:
        return None, False
    existing_part = (await db.execute(
        select(CommunityTelegramPart)
        .where(
            CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID,
            CommunityTelegramPart.telegram_message_id == telegram_message_id,
        )
        .options(
            selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.attachments),
            selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.telegram_parts),
        )
    )).scalar_one_or_none()
    if existing_part:
        logical = existing_part.message
        new_text = _telethon_message_text(telegram_message, logical)
        edit_date = getattr(telegram_message, "edit_date", None)
        changed = logical.text != new_text or logical.deleted_at is not None or existing_part.deleted_at is not None
        if changed:
            logical.text = new_text
            logical.deleted_at = None
            existing_part.deleted_at = None
            logical.edited_at = edit_date or ufa_now()
        elif edit_date and (logical.edited_at is None or edit_date > logical.edited_at):
            logical.edited_at = edit_date
            changed = True
        return logical, changed

    # Topic lifecycle/service records are represented by the topic model, not
    # as user-facing chat bubbles.
    if getattr(telegram_message, "action", None) is not None:
        return None, False

    sender = await telegram_message.get_sender()
    archived_app_name = _archived_app_author_name(telegram_message)
    if archived_app_name:
        digest = hashlib.sha256(archived_app_name.casefold().encode("utf-8")).digest()
        kind = "app_archive"
        peer_id = -int.from_bytes(digest[:7], "big")
        full_name = archived_app_name
    else:
        kind, peer_id, full_name = _telethon_author_snapshot(sender, telegram_message_id)
    linked_user = await get_user_by_telegram_user_id(db, peer_id) if kind == "user" and peer_id > 0 else None
    author = await _upsert_author(
        db,
        kind=kind,
        telegram_peer_id=peer_id,
        full_name=full_name,
        app_user_id=linked_user.id if linked_user else None,
        refresh_avatar=not bool(archived_app_name),
    )
    media_group_id = str(getattr(telegram_message, "grouped_id", "") or "") or None
    logical = None
    if media_group_id:
        logical = (await db.execute(
            select(CommunityMessage)
            .where(
                CommunityMessage.topic_id == topic.id,
                CommunityMessage.telegram_media_group_id == media_group_id,
            )
            .order_by(CommunityMessage.id.asc())
            .limit(1)
            .options(selectinload(CommunityMessage.attachments))
        )).scalar_one_or_none()
    if logical is None:
        reply_to_message_id = None
        reply_to_telegram_id = int(getattr(telegram_message, "reply_to_msg_id", 0) or 0)
        if reply_to_telegram_id:
            reply_part = (await db.execute(
                select(CommunityTelegramPart).where(
                    CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID,
                    CommunityTelegramPart.telegram_message_id == reply_to_telegram_id,
                )
            )).scalar_one_or_none()
            reply_to_message_id = reply_part.message_id if reply_part else None
        logical = CommunityMessage(
            topic_id=topic.id,
            author_id=author.id,
            app_user_id=linked_user.id if linked_user else None,
            reply_to_message_id=reply_to_message_id,
            source="telegram",
            telegram_media_group_id=media_group_id,
            text=_telethon_message_text(telegram_message),
            delivery_status="sent",
            sent_at=getattr(telegram_message, "date", None) or ufa_now(),
            edited_at=getattr(telegram_message, "edit_date", None),
        )
        db.add(logical)
        await db.flush()
    elif _telethon_message_text(telegram_message) and not logical.text:
        logical.text = _telethon_message_text(telegram_message)

    db.add(
        CommunityTelegramPart(
            message_id=logical.id,
            telegram_chat_id=TELEGRAM_COMMUNITY_CHAT_ID,
            telegram_message_id=telegram_message_id,
        )
    )
    await db.flush()
    await _store_telethon_attachment(db, client=client, telegram_message=telegram_message, logical=logical)
    if not topic.last_message_at or logical.sent_at >= topic.last_message_at:
        topic.last_message_id = logical.id
        topic.last_message_at = logical.sent_at
    return logical, True


async def _sync_telegram_forum_history_with_client(client: Any) -> dict[str, int]:
    peer = await _resolve_forum_peer(client)
    now = ufa_now()
    full_cutoff = now - timedelta(seconds=max(TELEGRAM_USERBOT_FULL_HISTORY_RECONCILE_SECONDS, 3600))
    imported = 0
    updated = 0
    deleted = 0
    scanned = 0
    async with get_session() as db:
        topics = list((await db.execute(
            select(CommunityTopic)
            .where(
                CommunityTopic.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID,
                CommunityTopic.is_deleted.is_(False),
            )
            .order_by(CommunityTopic.telegram_thread_id.asc())
        )).scalars().all())
        for topic in topics:
            if int(topic.telegram_thread_id) <= 0:
                continue
            full_reconcile = (
                not topic.telegram_history_complete
                or topic.telegram_history_synced_at is None
                or topic.telegram_history_synced_at < full_cutoff
            )
            min_id = 0 if full_reconcile else int(topic.telegram_history_max_message_id or 0)
            seen_ids: set[int] = set()
            async for telegram_message in client.iter_messages(
                peer,
                reply_to=topic.telegram_thread_id,
                min_id=min_id,
                reverse=True,
            ):
                telegram_message_id = int(getattr(telegram_message, "id", 0) or 0)
                if telegram_message_id <= 0:
                    continue
                seen_ids.add(telegram_message_id)
                scanned += 1
                existing = (await db.execute(
                    select(CommunityTelegramPart.id).where(
                        CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID,
                        CommunityTelegramPart.telegram_message_id == telegram_message_id,
                    )
                )).scalar_one_or_none()
                _, changed = await _upsert_telethon_message(
                    db,
                    client=client,
                    topic=topic,
                    telegram_message=telegram_message,
                )
                if changed:
                    if existing:
                        updated += 1
                    else:
                        imported += 1
                topic.telegram_history_min_message_id = min(
                    topic.telegram_history_min_message_id or telegram_message_id,
                    telegram_message_id,
                )
                topic.telegram_history_max_message_id = max(
                    topic.telegram_history_max_message_id or telegram_message_id,
                    telegram_message_id,
                )
                if scanned % 100 == 0:
                    await db.commit()

            if full_reconcile:
                stored_ids = set((await db.execute(
                    select(CommunityTelegramPart.telegram_message_id)
                    .join(CommunityMessage, CommunityMessage.id == CommunityTelegramPart.message_id)
                    .where(
                        CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID,
                        CommunityMessage.topic_id == topic.id,
                        CommunityTelegramPart.deleted_at.is_(None),
                        CommunityTelegramPart.created_at <= now,
                    )
                )).scalars().all())
                missing_ids = sorted(stored_ids - seen_ids)
                if missing_ids:
                    deleted += await mark_community_telegram_messages_deleted(db, missing_ids, deleted_at=now)
                topic.telegram_history_complete = True
            topic.telegram_history_synced_at = now
            await _refresh_topic_last_message(db, topic)
            await db.commit()
    return {"scanned": scanned, "imported": imported, "updated": updated, "deleted": deleted}


async def sync_telegram_forum_history() -> dict[str, int]:
    if not TELEGRAM_USERBOT_ENABLED:
        raise TelegramUserbotConfigurationError("Telegram userbot history sync is disabled")
    client = _build_client()
    await client.connect()
    try:
        await _require_authorized_user(client)
        return await _sync_telegram_forum_history_with_client(client)
    finally:
        await client.disconnect()
        _lock_down_session_file()


async def run_telegram_userbot_mirror(stop_event: asyncio.Event) -> None:
    """Continuously reconcile topics/history and receive Telegram edit/delete events."""
    from telethon import events

    retry_seconds = 10
    while not stop_event.is_set():
        client = _build_client(receive_updates=True)
        try:
            await client.connect()
            await _require_authorized_user(client)

            async def handle_edit(event: Any) -> None:
                if int(event.chat_id or 0) != TELEGRAM_COMMUNITY_CHAT_ID:
                    return
                try:
                    telegram_message_id = int(event.message.id)
                    async with get_session() as db:
                        part = (await db.execute(
                            select(CommunityTelegramPart)
                            .where(
                                CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID,
                                CommunityTelegramPart.telegram_message_id == telegram_message_id,
                            )
                            .options(selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.topic))
                        )).scalar_one_or_none()
                        if part:
                            await _upsert_telethon_message(
                                db,
                                client=client,
                                topic=part.message.topic,
                                telegram_message=event.message,
                            )
                            await db.commit()
                except Exception:
                    log.exception("telethon message edit mirror failed")

            async def handle_delete(event: Any) -> None:
                if int(event.chat_id or 0) != TELEGRAM_COMMUNITY_CHAT_ID:
                    return
                try:
                    async with get_session() as db:
                        count = await mark_community_telegram_messages_deleted(db, list(event.deleted_ids))
                        await db.commit()
                    if count:
                        log.info("telethon message deletions mirrored count=%s", count)
                except Exception:
                    log.exception("telethon message deletion mirror failed")

            client.add_event_handler(handle_edit, events.MessageEdited())
            client.add_event_handler(handle_delete, events.MessageDeleted())
            await client.catch_up()

            topic_result = await _sync_telegram_forum_topics_with_client(client)
            log.info(
                "telethon topics synchronized total=%s discovered=%s updated=%s restored=%s deleted=%s",
                topic_result.total,
                topic_result.discovered,
                topic_result.updated,
                topic_result.restored,
                topic_result.deleted,
            )
            history_result = await _sync_telegram_forum_history_with_client(client)
            log.info("telethon history synchronized %s", history_result)

            topic_interval = max(TELEGRAM_USERBOT_TOPIC_SYNC_INTERVAL_SECONDS, 60)
            history_interval = max(TELEGRAM_USERBOT_HISTORY_SYNC_INTERVAL_SECONDS, 60)
            loop = asyncio.get_running_loop()
            last_topic_sync = loop.time()
            last_history_sync = loop.time()
            while not stop_event.is_set() and client.is_connected():
                now_monotonic = loop.time()
                next_topic_in = max(topic_interval - (now_monotonic - last_topic_sync), 0.1)
                next_history_in = max(history_interval - (now_monotonic - last_history_sync), 0.1)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=min(next_topic_in, next_history_in))
                    continue
                except TimeoutError:
                    pass
                now_monotonic = loop.time()
                if now_monotonic - last_topic_sync >= topic_interval:
                    result = await _sync_telegram_forum_topics_with_client(client)
                    log.info("telethon topics reconciled total=%s", result.total)
                    last_topic_sync = now_monotonic
                if now_monotonic - last_history_sync >= history_interval:
                    result = await _sync_telegram_forum_history_with_client(client)
                    log.info("telethon history reconciled %s", result)
                    last_history_sync = now_monotonic
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("telethon mirror loop failed; reconnecting")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=retry_seconds)
            except TimeoutError:
                pass
        finally:
            if client.is_connected():
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
