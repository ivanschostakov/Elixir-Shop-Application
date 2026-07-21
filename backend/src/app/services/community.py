import hashlib
import hmac
import asyncio
import logging
import mimetypes
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request, UploadFile
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from config import (
    COMMUNITY_MEDIA_DIR,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_BOT_USERNAME,
    TELEGRAM_COMMUNITY_CHAT_ID,
    TELEGRAM_COMMUNITY_ENABLED,
    TELEGRAM_COMMUNITY_JOIN_URL,
    TELEGRAM_COMMUNITY_MAX_ATTACHMENT_BYTES,
    TELEGRAM_COMMUNITY_MAX_ATTACHMENTS,
    TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES,
    TELEGRAM_COMMUNITY_MAX_TOTAL_ATTACHMENT_BYTES,
    TELEGRAM_COMMUNITY_MEDIA_SIGNING_SECRET,
    TELEGRAM_COMMUNITY_MEMBERSHIP_CACHE_SECONDS,
    TELEGRAM_COMMUNITY_PROFILE_CACHE_SECONDS,
    ufa_now,
)
from src.database.schemas.community import (
    CommunityAttachmentRead,
    CommunityAuthorRead,
    CommunityGroupRead,
    CommunityMessagePageRead,
    CommunityMessageRead,
    CommunityReplyPreviewRead,
    CommunityStatusRead,
    CommunityTopicListRead,
    CommunityTopicRead,
)
from src.app.services.cache import get_cache_service
from src.app.services.upload_limits import read_upload_file_limited
from src.database.crud.auth.user import get_user_by_telegram_user_id
from src.database.models import (
    CommunityAttachment,
    CommunityAuthor,
    CommunityMessage,
    CommunityTelegramPart,
    CommunityTopic,
    CommunityTopicRead as CommunityTopicReadModel,
    User,
)
from src.integrations.telegram import TelegramBotAPIError, TelegramBotClient, get_telegram_bot_client

log = logging.getLogger(__name__)
COMMUNITY_AVATARS_DIR = COMMUNITY_MEDIA_DIR / "avatars"
COMMUNITY_ATTACHMENTS_DIR = COMMUNITY_MEDIA_DIR / "attachments"
COMMUNITY_GROUP_DIR = COMMUNITY_MEDIA_DIR / "group"
for _directory in (COMMUNITY_AVATARS_DIR, COMMUNITY_ATTACHMENTS_DIR, COMMUNITY_GROUP_DIR):
    _directory.mkdir(parents=True, exist_ok=True)


def _media_secret() -> bytes:
    value = TELEGRAM_COMMUNITY_MEDIA_SIGNING_SECRET or TELEGRAM_BOT_TOKEN or "community-media-disabled"
    return value.encode("utf-8")


def _media_signature(*, media_type: str, media_id: int, user_id: int, expires: int) -> str:
    payload = f"{media_type}:{media_id}:{user_id}:{expires}".encode("utf-8")
    return hmac.new(_media_secret(), payload, hashlib.sha256).hexdigest()


def build_community_media_url(request: Request, *, media_type: str, media_id: int, user_id: int) -> str:
    expires = int(time.time()) + 900
    signature = _media_signature(media_type=media_type, media_id=media_id, user_id=user_id, expires=expires)
    return str(request.url_for("get_community_media", media_type=media_type, media_id=media_id).include_query_params(uid=user_id, expires=expires, signature=signature))


def verify_community_media_signature(*, media_type: str, media_id: int, user_id: int, expires: int, signature: str) -> bool:
    if expires < int(time.time()): return False
    expected = _media_signature(media_type=media_type, media_id=media_id, user_id=user_id, expires=expires)
    return hmac.compare_digest(signature, expected)


async def resolve_community_media_path(db: AsyncSession, *, media_type: str, media_id: int) -> tuple[Path, str | None] | None:
    if media_type == "author":
        author = await db.get(CommunityAuthor, media_id)
        return (COMMUNITY_AVATARS_DIR / author.avatar_local_filename, "image/jpeg") if author and author.avatar_local_filename else None
    if media_type == "attachment":
        attachment = await db.get(CommunityAttachment, media_id)
        return (COMMUNITY_ATTACHMENTS_DIR / attachment.local_filename, attachment.mime_type) if attachment and attachment.local_filename else None
    if media_type == "group" and media_id == 0:
        path = COMMUNITY_GROUP_DIR / "avatar"
        return (path, "image/jpeg") if path.exists() else None
    return None


def _membership_cache_key(telegram_user_id: int) -> str:
    return f"telegram:community:membership:{TELEGRAM_COMMUNITY_CHAT_ID}:{telegram_user_id}"


async def invalidate_community_membership(telegram_user_id: int) -> None:
    client = get_cache_service().client
    if client is not None:
        try:
            await client.delete(_membership_cache_key(telegram_user_id))
        except Exception:
            log.exception("community membership cache invalidation failed")


def _is_active_member(member: dict[str, Any]) -> bool:
    member_status = str(member.get("status") or "")
    if member_status in {"creator", "administrator", "member"}: return True
    return member_status == "restricted" and bool(member.get("is_member"))


async def _membership_access(user: User, *, refresh: bool = False, telegram_client: TelegramBotClient | None = None) -> str:
    del user, refresh, telegram_client
    if not TELEGRAM_COMMUNITY_ENABLED or not TELEGRAM_COMMUNITY_CHAT_ID or not (TELEGRAM_BOT_TOKEN or "").strip():
        return "temporarily_unavailable"
    # The app community is app-native. Telegram is a transport/mirror and never
    # an identity or membership prerequisite for an authenticated app user.
    return "granted"


def _action_url(access: str) -> str | None:
    if access == "telegram_link_required" and TELEGRAM_BOT_USERNAME: return f"https://t.me/{TELEGRAM_BOT_USERNAME}?start=link"
    if access == "membership_required": return TELEGRAM_COMMUNITY_JOIN_URL
    return None


async def get_community_status(db: AsyncSession, *, user: User, request: Request, refresh: bool = False, telegram_client: TelegramBotClient | None = None) -> CommunityStatusRead:
    access = await _membership_access(user, refresh=refresh, telegram_client=telegram_client)
    group: CommunityGroupRead | None = None
    if TELEGRAM_COMMUNITY_ENABLED and TELEGRAM_COMMUNITY_CHAT_ID:
        title = "Our Group"
        try:
            info = await (telegram_client or get_telegram_bot_client()).get_chat(TELEGRAM_COMMUNITY_CHAT_ID)
            title = str(info.get("title") or title)
            photo = info.get("photo") if isinstance(info.get("photo"), dict) else None
            file_id = str(photo.get("big_file_id") or photo.get("small_file_id") or "") if photo else ""
            group_path = COMMUNITY_GROUP_DIR / "avatar"
            if file_id and not group_path.exists():
                await (telegram_client or get_telegram_bot_client()).download_file(file_id, group_path, max_bytes=TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES)
        except (TelegramBotAPIError, TimeoutError, OSError):
            pass
        group_path = COMMUNITY_GROUP_DIR / "avatar"
        group = CommunityGroupRead(title=title, image_url=build_community_media_url(request, media_type="group", media_id=0, user_id=user.id) if group_path.exists() else None)
    return CommunityStatusRead(enabled=TELEGRAM_COMMUNITY_ENABLED, access=access, group=group, action_url=_action_url(access))


async def require_community_access(user: User, *, telegram_client: TelegramBotClient | None = None) -> None:
    access = await _membership_access(user, telegram_client=telegram_client)
    if access != "granted":
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE if access == "temporarily_unavailable" else status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=http_status, detail={"code": access, "message": "The community is temporarily unavailable"})


def _message_options():
    return (
        selectinload(CommunityMessage.author),
        selectinload(CommunityMessage.attachments),
        selectinload(CommunityMessage.telegram_parts),
        selectinload(CommunityMessage.reply_to).selectinload(CommunityMessage.author),
    )


def _telegram_message_url(message: CommunityMessage) -> str | None:
    active_parts = [part for part in message.telegram_parts if part.deleted_at is None]
    if not active_parts: return TELEGRAM_COMMUNITY_JOIN_URL
    telegram_message_id = active_parts[0].telegram_message_id
    internal_chat_id = str(abs(TELEGRAM_COMMUNITY_CHAT_ID))
    if internal_chat_id.startswith("100"): internal_chat_id = internal_chat_id[3:]
    thread = message.topic.telegram_thread_id if message.topic else 0
    suffix = f"?thread={thread}" if thread else ""
    return f"https://t.me/c/{internal_chat_id}/{telegram_message_id}{suffix}"


def serialize_community_message(message: CommunityMessage, *, request: Request, user_id: int) -> CommunityMessageRead:
    author = message.author
    author_read = CommunityAuthorRead(id=author.id if author else 0, full_name=author.full_name if author else "Telegram member", avatar_url=build_community_media_url(request, media_type="author", media_id=author.id, user_id=user_id) if author and author.avatar_local_filename else None, is_current_user=message.app_user_id == user_id)
    attachments = [] if message.deleted_at else [CommunityAttachmentRead(id=item.id, kind=item.kind, filename=item.original_filename or item.filename, mime_type=item.mime_type, size_bytes=item.size_bytes, media_url=build_community_media_url(request, media_type="attachment", media_id=item.id, user_id=user_id) if item.local_filename and item.status == "ready" else None, available_in_telegram=not bool(item.local_filename)) for item in message.attachments]
    reply = None
    if message.reply_to:
        reply = CommunityReplyPreviewRead(id=message.reply_to.id, author_name=message.reply_to.author.full_name if message.reply_to.author else "Telegram member", text=(message.reply_to.text or "Attachment")[:160])
    can_mutate = message.source == "app" and message.app_user_id == user_id and not message.deleted_at
    return CommunityMessageRead(id=message.id, topic_id=message.topic_id, author=author_read, text="" if message.deleted_at else message.text, attachments=attachments, reply_to=reply, unsupported_type=None if message.deleted_at else message.unsupported_type, telegram_url=_telegram_message_url(message), delivery_status=message.delivery_status, is_edited=bool(message.edited_at), is_deleted=bool(message.deleted_at), can_edit=can_mutate, can_delete=can_mutate, edited_at=message.edited_at, created_at=message.sent_at)


async def _initialize_read_baseline(db: AsyncSession, *, user_id: int, topics: list[CommunityTopic]) -> None:
    existing_count = int((await db.execute(select(func.count(CommunityTopicReadModel.id)).where(CommunityTopicReadModel.user_id == user_id))).scalar_one())
    if existing_count or not topics: return
    for topic in topics:
        db.add(CommunityTopicReadModel(user_id=user_id, topic_id=topic.id, last_read_message_id=topic.last_message_id))
    await db.commit()


async def list_community_topics(db: AsyncSession, *, user: User, request: Request) -> CommunityTopicListRead:
    await require_community_access(user)
    topics = list((await db.execute(select(CommunityTopic).where(CommunityTopic.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTopic.is_hidden.is_(False), CommunityTopic.is_deleted.is_(False)).order_by(CommunityTopic.last_message_at.desc().nullslast(), CommunityTopic.name.asc()))).scalars().all())
    await _initialize_read_baseline(db, user_id=user.id, topics=topics)
    read_states = list((await db.execute(select(CommunityTopicReadModel).where(CommunityTopicReadModel.user_id == user.id, CommunityTopicReadModel.topic_id.in_([topic.id for topic in topics]) if topics else False))).scalars().all())
    read_by_topic = {item.topic_id: item for item in read_states}
    topic_reads: list[CommunityTopicRead] = []
    total_unread = 0
    for topic in topics:
        last_message = None
        if topic.last_message_id:
            stmt = select(CommunityMessage).where(CommunityMessage.id == topic.last_message_id).options(*_message_options())
            last_message = (await db.execute(stmt)).scalar_one_or_none()
            if last_message: last_message.topic = topic
        last_read_id = read_by_topic.get(topic.id).last_read_message_id if read_by_topic.get(topic.id) else None
        unread_stmt = select(func.count(CommunityMessage.id)).where(CommunityMessage.topic_id == topic.id, CommunityMessage.id > int(last_read_id or 0), CommunityMessage.deleted_at.is_(None), or_(CommunityMessage.app_user_id.is_(None), CommunityMessage.app_user_id != user.id))
        unread = int((await db.execute(unread_stmt)).scalar_one())
        total_unread += unread
        topic_reads.append(CommunityTopicRead(id=topic.id, name=topic.name, icon_color=topic.icon_color, icon_custom_emoji_id=topic.icon_custom_emoji_id, is_closed=topic.is_closed, last_message=serialize_community_message(last_message, request=request, user_id=user.id) if last_message else None, unread_count=unread))
    return CommunityTopicListRead(topics=topic_reads, total_unread=total_unread)


async def list_community_messages(db: AsyncSession, *, user: User, request: Request, topic_id: int, before_id: int | None, after_id: int | None, changed_after: datetime | None, changed_after_id: int, limit: int) -> CommunityMessagePageRead:
    await require_community_access(user)
    sync_cursor = ufa_now()
    sync_cursor_id = 0
    if before_id and after_id: raise HTTPException(status_code=422, detail="before_id and after_id cannot be combined")
    topic = await db.get(CommunityTopic, topic_id)
    if topic is None or topic.telegram_chat_id != TELEGRAM_COMMUNITY_CHAT_ID or topic.is_deleted: raise HTTPException(status_code=404, detail="Community topic not found")
    stmt = select(CommunityMessage).where(CommunityMessage.topic_id == topic_id).options(*_message_options())
    if after_id:
        new_rows = list((await db.execute(stmt.where(CommunityMessage.id > after_id).order_by(CommunityMessage.id.asc()).limit(limit + 1))).scalars().all())
        has_more = len(new_rows) > limit
        new_rows = new_rows[:limit]
        if changed_after:
            changed_rows = list((await db.execute(
                select(CommunityMessage)
                .where(
                    CommunityMessage.topic_id == topic_id,
                    CommunityMessage.id <= after_id,
                    or_(
                        CommunityMessage.updated_at > changed_after,
                        and_(
                            CommunityMessage.updated_at == changed_after,
                            CommunityMessage.id > changed_after_id,
                        ),
                    ),
                    CommunityMessage.updated_at <= sync_cursor,
                )
                .order_by(CommunityMessage.updated_at.asc(), CommunityMessage.id.asc())
                .limit(limit + 1)
                .options(*_message_options())
            )).scalars().all())
            changed_has_more = len(changed_rows) > limit
            has_more = has_more or changed_has_more
            changed_rows = changed_rows[:limit]
            if changed_has_more and changed_rows:
                sync_cursor = changed_rows[-1].updated_at
                sync_cursor_id = changed_rows[-1].id
        else:
            # Backward-compatible reconciliation for clients without a change cursor.
            changed_rows = list((await db.execute(
                select(CommunityMessage)
                .where(CommunityMessage.topic_id == topic_id, CommunityMessage.id <= after_id)
                .order_by(CommunityMessage.id.desc())
                .limit(20)
                .options(*_message_options())
            )).scalars().all())
        rows = sorted({row.id: row for row in [*changed_rows, *new_rows]}.values(), key=lambda row: row.id)
    else:
        if before_id: stmt = stmt.where(CommunityMessage.id < before_id)
        stmt = stmt.order_by(CommunityMessage.id.desc())
        rows = list((await db.execute(stmt.limit(limit + 1))).scalars().all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        rows.reverse()
    for row in rows: row.topic = topic
    return CommunityMessagePageRead(messages=[serialize_community_message(row, request=request, user_id=user.id) for row in rows], has_more=has_more, oldest_id=rows[0].id if rows else None, newest_id=rows[-1].id if rows else None, sync_cursor=sync_cursor, sync_cursor_id=sync_cursor_id)


async def mark_community_topic_read(db: AsyncSession, *, user: User, topic_id: int, last_message_id: int) -> None:
    await require_community_access(user)
    message = await db.get(CommunityMessage, last_message_id)
    if message is None or message.topic_id != topic_id: raise HTTPException(status_code=404, detail="Community message not found")
    read_state = (await db.execute(select(CommunityTopicReadModel).where(CommunityTopicReadModel.user_id == user.id, CommunityTopicReadModel.topic_id == topic_id))).scalar_one_or_none()
    if read_state is None: db.add(CommunityTopicReadModel(user_id=user.id, topic_id=topic_id, last_read_message_id=last_message_id))
    elif not read_state.last_read_message_id or last_message_id > read_state.last_read_message_id: read_state.last_read_message_id = last_message_id
    await db.commit()


async def _upsert_author(db: AsyncSession, *, kind: str, telegram_peer_id: int, full_name: str, app_user_id: int | None = None, telegram_client: TelegramBotClient | None = None, refresh_avatar: bool = True) -> CommunityAuthor:
    author = (await db.execute(select(CommunityAuthor).where(CommunityAuthor.kind == kind, CommunityAuthor.telegram_peer_id == telegram_peer_id))).scalar_one_or_none()
    if author is None:
        author = CommunityAuthor(kind=kind, telegram_peer_id=telegram_peer_id, app_user_id=app_user_id, full_name=full_name or "Telegram member")
        db.add(author); await db.flush()
    else:
        author.full_name = full_name or author.full_name
        if app_user_id: author.app_user_id = app_user_id
    now = ufa_now()
    stale = author.avatar_refreshed_at is None or author.avatar_refreshed_at < now - timedelta(seconds=TELEGRAM_COMMUNITY_PROFILE_CACHE_SECONDS)
    if stale and refresh_avatar:
        author.avatar_refreshed_at = now
        try:
            client = telegram_client or get_telegram_bot_client()
            photo = await client.get_user_profile_photo(telegram_peer_id) if kind == "user" else (await client.get_chat(telegram_peer_id)).get("photo")
            file_id = str((photo or {}).get("file_id") or (photo or {}).get("big_file_id") or (photo or {}).get("small_file_id") or "")
            if file_id and file_id != author.avatar_file_id:
                filename = f"{kind}-{telegram_peer_id}-{uuid4().hex}"
                await client.download_file(file_id, COMMUNITY_AVATARS_DIR / filename, max_bytes=TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES)
                if author.avatar_local_filename: (COMMUNITY_AVATARS_DIR / author.avatar_local_filename).unlink(missing_ok=True)
                author.avatar_file_id = file_id; author.avatar_local_filename = filename
        except (TelegramBotAPIError, TimeoutError, OSError):
            log.info("community author avatar refresh skipped peer_id=%s", telegram_peer_id)
    return author


def _safe_filename(value: str | None, fallback: str) -> str:
    normalized = Path((value or "").strip()).name
    return normalized[:255] or fallback


async def create_community_message(db: AsyncSession, *, user: User, request: Request, topic_id: int, client_id: str, text: str, reply_to_message_id: int | None, uploads: list[UploadFile]) -> CommunityMessageRead:
    await require_community_access(user)
    topic = await db.get(CommunityTopic, topic_id)
    if topic is None or topic.telegram_chat_id != TELEGRAM_COMMUNITY_CHAT_ID or topic.is_deleted: raise HTTPException(status_code=404, detail="Community topic not found")
    if topic.is_closed: raise HTTPException(status_code=409, detail="This Telegram topic is closed")
    normalized_text = text.strip()
    if not normalized_text and not uploads: raise HTTPException(status_code=422, detail="Message text or an attachment is required")
    if len(uploads) > TELEGRAM_COMMUNITY_MAX_ATTACHMENTS: raise HTTPException(status_code=413, detail="Too many attachments")
    normalized_client_id = client_id.strip()
    if not normalized_client_id: raise HTTPException(status_code=422, detail="client_id must not be empty")
    existing_stmt = select(CommunityMessage).where(CommunityMessage.app_user_id == user.id, CommunityMessage.client_id == normalized_client_id).options(*_message_options())
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        existing.topic = topic
        return serialize_community_message(existing, request=request, user_id=user.id)
    reply_to = await db.get(CommunityMessage, reply_to_message_id) if reply_to_message_id else None
    if reply_to_message_id and (reply_to is None or reply_to.topic_id != topic_id): raise HTTPException(status_code=422, detail="Reply target is not in this topic")
    prepared_uploads: list[tuple[str, str, bytes]] = []
    total_bytes = 0
    for index, upload in enumerate(uploads):
        content = await read_upload_file_limited(upload, max_bytes=TELEGRAM_COMMUNITY_MAX_ATTACHMENT_BYTES, label="Community attachment")
        total_bytes += len(content)
        if total_bytes > TELEGRAM_COMMUNITY_MAX_TOTAL_ATTACHMENT_BYTES: raise HTTPException(status_code=413, detail="Community attachments exceed the total size limit")
        original = _safe_filename(upload.filename, f"attachment-{index + 1}")
        mime_type = upload.content_type or mimetypes.guess_type(original)[0] or "application/octet-stream"
        prepared_uploads.append((original, mime_type, content))
    author = await _upsert_author(db, kind="app", telegram_peer_id=user.id, full_name=" ".join(part for part in (user.name, user.surname) if part).strip() or "Elixir member", app_user_id=user.id, refresh_avatar=False)
    message = CommunityMessage(topic_id=topic.id, author_id=author.id, app_user_id=user.id, reply_to_message_id=reply_to.id if reply_to else None, source="app", client_id=normalized_client_id, text=normalized_text, delivery_status="queued", sent_at=ufa_now())
    db.add(message); await db.flush()
    written_paths: list[Path] = []
    for original, mime_type, content in prepared_uploads:
        local_filename = f"{message.id}-{uuid4().hex}"
        target_path = COMMUNITY_ATTACHMENTS_DIR / local_filename
        target_path.write_bytes(content); written_paths.append(target_path)
        kind = "image" if mime_type.startswith("image/") else "document"
        db.add(CommunityAttachment(message_id=message.id, kind=kind, original_filename=original, filename=local_filename, mime_type=mime_type, size_bytes=len(content), local_filename=local_filename, status="ready"))
    topic.last_message_id = message.id; topic.last_message_at = message.sent_at
    try: await db.commit()
    except Exception:
        for path in written_paths: path.unlink(missing_ok=True)
        raise
    stmt = select(CommunityMessage).where(CommunityMessage.id == message.id).options(*_message_options())
    message = (await db.execute(stmt)).scalar_one(); message.topic = topic
    return serialize_community_message(message, request=request, user_id=user.id)


async def _refresh_topic_last_message(db: AsyncSession, topic: CommunityTopic) -> None:
    latest = (await db.execute(
        select(CommunityMessage)
        .where(CommunityMessage.topic_id == topic.id, CommunityMessage.deleted_at.is_(None))
        .order_by(CommunityMessage.sent_at.desc(), CommunityMessage.id.desc())
        .limit(1)
    )).scalar_one_or_none()
    topic.last_message_id = latest.id if latest else None
    topic.last_message_at = latest.sent_at if latest else None


def _soft_delete_message(message: CommunityMessage, *, deleted_at: datetime | None = None) -> None:
    when = deleted_at or ufa_now()
    message.deleted_at = when
    message.text = ""
    message.unsupported_type = None
    for attachment in message.attachments:
        if attachment.local_filename:
            (COMMUNITY_ATTACHMENTS_DIR / attachment.local_filename).unlink(missing_ok=True)
        attachment.local_filename = None
        attachment.status = "deleted"


async def edit_community_message(
    db: AsyncSession,
    *,
    user: User,
    request: Request,
    topic_id: int,
    message_id: int,
    text: str,
    telegram_client: TelegramBotClient | None = None,
) -> CommunityMessageRead:
    await require_community_access(user)
    normalized_text = text.strip()
    if not normalized_text:
        raise HTTPException(status_code=422, detail="Message text must not be empty")
    message = (await db.execute(
        select(CommunityMessage)
        .where(CommunityMessage.id == message_id, CommunityMessage.topic_id == topic_id)
        .options(*_message_options(), selectinload(CommunityMessage.topic))
    )).scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="Community message not found")
    if message.app_user_id != user.id or message.source != "app":
        raise HTTPException(status_code=403, detail="You can edit only your own app messages")
    if message.deleted_at:
        raise HTTPException(status_code=409, detail="Deleted messages cannot be edited")

    edited_at = ufa_now()
    if message.delivery_status in {"queued", "failed"} and not message.telegram_parts:
        message.text = normalized_text
        message.edited_at = edited_at
        await db.commit()
    else:
        author_name, header = _telegram_app_header(message)
        rendered = f"{header}\n\n{normalized_text}"
        active_parts = [part for part in message.telegram_parts if part.deleted_at is None]
        attachment_part_ids = {
            int(attachment.telegram_message_id)
            for attachment in message.attachments
            if attachment.telegram_message_id
        }
        text_parts = [part for part in active_parts if part.telegram_message_id not in attachment_part_ids]
        client = telegram_client or get_telegram_bot_client()
        try:
            if text_parts:
                if len(rendered) > 4096:
                    raise HTTPException(status_code=422, detail="Edited message is too long for Telegram")
                await client.call(
                    "editMessageText",
                    data={
                        "chat_id": TELEGRAM_COMMUNITY_CHAT_ID,
                        "message_id": text_parts[0].telegram_message_id,
                        "text": rendered,
                        "entities": _telegram_author_entities(rendered, author_name),
                    },
                )
                extra_ids = [part.telegram_message_id for part in text_parts[1:]]
                if extra_ids:
                    await client.call(
                        "deleteMessages",
                        data={"chat_id": TELEGRAM_COMMUNITY_CHAT_ID, "message_ids": extra_ids},
                    )
                    for part in text_parts[1:]:
                        part.deleted_at = edited_at
            elif active_parts and attachment_part_ids:
                if len(rendered) > 1024:
                    raise HTTPException(status_code=422, detail="Edited attachment caption is too long for Telegram")
                target = next(
                    (part for part in active_parts if part.telegram_message_id in attachment_part_ids),
                    active_parts[0],
                )
                await client.call(
                    "editMessageCaption",
                    data={
                        "chat_id": TELEGRAM_COMMUNITY_CHAT_ID,
                        "message_id": target.telegram_message_id,
                        "caption": rendered,
                        "caption_entities": _telegram_author_entities(rendered, author_name),
                    },
                )
            else:
                raise HTTPException(status_code=409, detail="This message has not been delivered to Telegram yet")
        except (TelegramBotAPIError, TimeoutError, OSError) as exc:
            raise HTTPException(status_code=502, detail="Telegram could not edit this message") from exc
        message.text = normalized_text
        message.edited_at = edited_at
        await db.commit()

    message = (await db.execute(
        select(CommunityMessage)
        .where(CommunityMessage.id == message_id)
        .options(*_message_options(), selectinload(CommunityMessage.topic))
    )).scalar_one()
    return serialize_community_message(message, request=request, user_id=user.id)


async def delete_community_message(
    db: AsyncSession,
    *,
    user: User,
    topic_id: int,
    message_id: int,
    telegram_client: TelegramBotClient | None = None,
) -> None:
    await require_community_access(user)
    message = (await db.execute(
        select(CommunityMessage)
        .where(CommunityMessage.id == message_id, CommunityMessage.topic_id == topic_id)
        .options(
            selectinload(CommunityMessage.attachments),
            selectinload(CommunityMessage.telegram_parts),
            selectinload(CommunityMessage.topic),
        )
    )).scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="Community message not found")
    if message.app_user_id != user.id or message.source != "app":
        raise HTTPException(status_code=403, detail="You can delete only your own app messages")
    if message.deleted_at:
        return
    active_parts = [part for part in message.telegram_parts if part.deleted_at is None]
    if active_parts:
        try:
            await (telegram_client or get_telegram_bot_client()).call(
                "deleteMessages",
                data={
                    "chat_id": TELEGRAM_COMMUNITY_CHAT_ID,
                    "message_ids": [part.telegram_message_id for part in active_parts],
                },
            )
        except (TelegramBotAPIError, TimeoutError, OSError) as exc:
            raise HTTPException(status_code=502, detail="Telegram could not delete this message") from exc
    deleted_at = ufa_now()
    for part in active_parts:
        part.deleted_at = deleted_at
    _soft_delete_message(message, deleted_at=deleted_at)
    await _refresh_topic_last_message(db, message.topic)
    await db.commit()


async def mark_community_telegram_messages_deleted(
    db: AsyncSession,
    telegram_message_ids: list[int],
    *,
    deleted_at: datetime | None = None,
) -> int:
    normalized_ids = sorted({int(message_id) for message_id in telegram_message_ids if int(message_id) > 0})
    if not normalized_ids:
        return 0
    parts = list((await db.execute(
        select(CommunityTelegramPart)
        .where(
            CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID,
            CommunityTelegramPart.telegram_message_id.in_(normalized_ids),
        )
        .options(
            selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.telegram_parts),
            selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.attachments),
            selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.topic),
        )
    )).scalars().all())
    when = deleted_at or ufa_now()
    affected_messages: dict[int, CommunityMessage] = {}
    for part in parts:
        part.deleted_at = when
        affected_messages[part.message_id] = part.message
        for attachment in part.message.attachments:
            if attachment.telegram_message_id == part.telegram_message_id:
                if attachment.local_filename:
                    (COMMUNITY_ATTACHMENTS_DIR / attachment.local_filename).unlink(missing_ok=True)
                attachment.local_filename = None
                attachment.status = "deleted"
    affected_topics: dict[int, CommunityTopic] = {}
    for message in affected_messages.values():
        if all(part.deleted_at is not None for part in message.telegram_parts):
            _soft_delete_message(message, deleted_at=when)
            affected_topics[message.topic.id] = message.topic
    for topic in affected_topics.values():
        await _refresh_topic_last_message(db, topic)
    return len(parts)


async def _reply_parameters(message: CommunityMessage) -> dict[str, Any] | None:
    if not message.reply_to: return None
    active_parts = [part for part in message.reply_to.telegram_parts if part.deleted_at is None]
    if not active_parts: return None
    return {"message_id": active_parts[0].telegram_message_id, "allow_sending_without_reply": True}


def _telegram_text_chunks(value: str, limit: int = 4096) -> list[str]:
    remaining = value.strip()
    chunks: list[str] = []
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        split_at = max(remaining.rfind("\n", 0, limit + 1), remaining.rfind(" ", 0, limit + 1))
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    return chunks


def _telegram_app_header(message: CommunityMessage) -> tuple[str, str]:
    author_name = message.author.full_name if message.author else "Elixir member"
    message_kind = "↩️" if message.reply_to else "💬"
    return author_name, f"{author_name} · {message_kind} Приложение"


def _telegram_author_entities(value: str, author_name: str) -> list[dict[str, Any]]:
    if not author_name or not value.startswith(author_name):
        return []
    # Telegram entity offsets and lengths use UTF-16 code units.
    author_length = len(author_name.encode("utf-16-le")) // 2
    return [{"type": "bold", "offset": 0, "length": author_length}]


async def recover_stale_community_deliveries(db: AsyncSession, *, older_than_seconds: int = 300) -> int:
    if not TELEGRAM_COMMUNITY_ENABLED or not TELEGRAM_COMMUNITY_CHAT_ID:
        return 0
    cutoff = ufa_now() - timedelta(seconds=max(older_than_seconds, 60))
    result = await db.execute(
        update(CommunityMessage)
        .where(
            CommunityMessage.source == "app",
            CommunityMessage.delivery_status == "sending",
            CommunityMessage.updated_at < cutoff,
        )
        .values(
            delivery_status="delivery_unknown",
            delivery_error="Delivery was interrupted; check Telegram before retrying.",
        )
    )
    await db.commit()
    return int(result.rowcount or 0)


async def relay_next_community_message(db: AsyncSession, *, telegram_client: TelegramBotClient | None = None) -> bool:
    if not TELEGRAM_COMMUNITY_ENABLED or not TELEGRAM_COMMUNITY_CHAT_ID:
        return False
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
    common: dict[str, Any] = {"chat_id": TELEGRAM_COMMUNITY_CHAT_ID, "message_thread_id": message.topic.telegram_thread_id or None, "reply_parameters": await _reply_parameters(message)}
    sent_results: list[dict[str, Any]] = []

    async def store_result(result: Any) -> None:
        if not isinstance(result, dict):
            return
        sent_results.append(result)
        telegram_message_id = int(result.get("message_id") or 0)
        if telegram_message_id:
            db.add(CommunityTelegramPart(message_id=message.id, telegram_chat_id=TELEGRAM_COMMUNITY_CHAT_ID, telegram_message_id=telegram_message_id))
            await db.commit()

    async def send_text_parts(value: str) -> None:
        for chunk in _telegram_text_chunks(value):
            if sent_results:
                await asyncio.sleep(3)
            result = await client.call("sendMessage", data={**common, "text": chunk, "entities": _telegram_author_entities(chunk, author_name)})
            await store_result(result)
            common["reply_parameters"] = None

    try:
        if not message.attachments:
            await send_text_parts(text)
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
                if isinstance(result, dict):
                    attachment.telegram_message_id = int(result.get("message_id") or 0) or None
                await store_result(result)
                common["reply_parameters"] = None
        message.delivery_status = "sent"; message.next_delivery_attempt_at = None
        await db.commit(); return True
    except TelegramBotAPIError as exc:
        if exc.retry_after and not sent_results:
            message.delivery_status = "queued"; message.next_delivery_attempt_at = ufa_now() + timedelta(seconds=max(exc.retry_after, 1))
        elif sent_results:
            message.delivery_status = "delivery_unknown"
        else:
            message.delivery_status = "failed"
        message.delivery_error = str(exc)[:1000]; await db.commit(); return True
    except (TimeoutError, OSError) as exc:
        message.delivery_status = "delivery_unknown"; message.delivery_error = str(exc)[:1000]
        await db.commit(); return True


def _message_full_name(sender: dict[str, Any]) -> str:
    return " ".join(str(sender.get(key) or "").strip() for key in ("first_name", "last_name")).strip() or "Telegram member"


async def _get_or_create_topic(db: AsyncSession, *, thread_id: int, name: str | None = None) -> CommunityTopic:
    topic = (await db.execute(select(CommunityTopic).where(CommunityTopic.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTopic.telegram_thread_id == thread_id))).scalar_one_or_none()
    if topic is None:
        topic = CommunityTopic(telegram_chat_id=TELEGRAM_COMMUNITY_CHAT_ID, telegram_thread_id=thread_id, name=(name or ("General" if thread_id == 0 else f"Topic {thread_id}"))[:128])
        db.add(topic); await db.flush()
    elif name: topic.name = name[:128]
    topic.is_deleted = False
    return topic


async def _is_group_admin(telegram_client: TelegramBotClient, user_id: int) -> bool:
    try: return str((await telegram_client.get_chat_member(TELEGRAM_COMMUNITY_CHAT_ID, user_id)).get("status") or "") in {"creator", "administrator"}
    except (TelegramBotAPIError, TimeoutError): return False


async def process_community_telegram_message(db: AsyncSession, payload: dict[str, Any], *, telegram_client: TelegramBotClient | None = None) -> dict[str, Any]:
    is_edit = isinstance(payload.get("edited_message"), dict)
    message = payload.get("edited_message") if is_edit else payload.get("message")
    if not isinstance(message, dict): return {"ok": True, "ignored": "no community message"}
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    if not TELEGRAM_COMMUNITY_ENABLED or int(chat.get("id") or 0) != TELEGRAM_COMMUNITY_CHAT_ID: return {"ok": True, "ignored": "wrong community chat"}
    telegram_message_id = int(message.get("message_id") or 0)
    existing_part = (await db.execute(
        select(CommunityTelegramPart)
        .where(
            CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID,
            CommunityTelegramPart.telegram_message_id == telegram_message_id,
        )
        .options(selectinload(CommunityTelegramPart.message))
    )).scalar_one_or_none()
    if existing_part:
        if not is_edit:
            return {"ok": True, "ignored": "duplicate"}
        logical = existing_part.message
        raw_text = str(message.get("text") or message.get("caption") or "")
        if logical.source == "app" and "\n\n" in raw_text:
            raw_text = raw_text.split("\n\n", 1)[1]
        logical.text = raw_text
        logical.edited_at = datetime.fromtimestamp(
            int(message.get("edit_date") or time.time()),
            tz=ufa_now().tzinfo,
        )
        logical.deleted_at = None
        existing_part.deleted_at = None
        return {"ok": True, "community_message_id": logical.id, "edited": True}
    client = telegram_client or get_telegram_bot_client()
    thread_id = int(message.get("message_thread_id") or 0)
    sender = message.get("from") if isinstance(message.get("from"), dict) else {}
    raw_text = str(message.get("text") or message.get("caption") or "")
    if raw_text.startswith("/register"):
        sender_id = int(sender.get("id") or 0)
        if not sender_id or not await _is_group_admin(client, sender_id): return {"ok": True, "ignored": "register requires admin"}
        name = raw_text.partition(" ")[2].strip() or ("General" if thread_id == 0 else f"Topic {thread_id}")
        await _get_or_create_topic(db, thread_id=thread_id, name=name); await db.commit()
        try: await client.delete_message(TELEGRAM_COMMUNITY_CHAT_ID, telegram_message_id)
        except (TelegramBotAPIError, TimeoutError): pass
        return {"ok": True, "registered_thread_id": thread_id}
    created = message.get("forum_topic_created") if isinstance(message.get("forum_topic_created"), dict) else None
    edited = message.get("forum_topic_edited") if isinstance(message.get("forum_topic_edited"), dict) else None
    topic = await _get_or_create_topic(db, thread_id=thread_id, name=str((created or edited or {}).get("name") or "") or None)
    if created:
        topic.icon_color = created.get("icon_color"); topic.icon_custom_emoji_id = created.get("icon_custom_emoji_id")
    if edited and "icon_custom_emoji_id" in edited:
        topic.icon_custom_emoji_id = edited.get("icon_custom_emoji_id") or None
    if message.get("forum_topic_closed") is not None: topic.is_closed = True
    if message.get("forum_topic_reopened") is not None: topic.is_closed = False
    if message.get("general_forum_topic_hidden") is not None: topic.is_hidden = True
    if message.get("general_forum_topic_unhidden") is not None: topic.is_hidden = False
    if created or edited or message.get("forum_topic_closed") is not None or message.get("forum_topic_reopened") is not None or message.get("general_forum_topic_hidden") is not None or message.get("general_forum_topic_unhidden") is not None:
        await db.commit(); return {"ok": True, "topic_updated": topic.id}
    sender_chat = message.get("sender_chat") if isinstance(message.get("sender_chat"), dict) else None
    if sender_chat:
        peer_id = int(sender_chat.get("id") or 0); kind = "chat"; full_name = str(sender_chat.get("title") or "Telegram")
    else:
        peer_id = int(sender.get("id") or 0); kind = "user"; full_name = _message_full_name(sender)
    linked_user = await get_user_by_telegram_user_id(db, peer_id) if kind == "user" and peer_id else None
    author = await _upsert_author(db, kind=kind, telegram_peer_id=peer_id or -telegram_message_id, full_name=full_name, app_user_id=linked_user.id if linked_user else None, telegram_client=client, refresh_avatar=False)
    media_group_id = str(message.get("media_group_id") or "") or None
    logical = None
    if media_group_id:
        logical = (await db.execute(select(CommunityMessage).where(CommunityMessage.topic_id == topic.id, CommunityMessage.telegram_media_group_id == media_group_id).order_by(CommunityMessage.id.asc()).limit(1))).scalar_one_or_none()
    if logical is None:
        reply_to = None
        reply_payload = message.get("reply_to_message") if isinstance(message.get("reply_to_message"), dict) else None
        if reply_payload:
            reply_part = (await db.execute(select(CommunityTelegramPart).where(CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTelegramPart.telegram_message_id == int(reply_payload.get("message_id") or 0)))).scalar_one_or_none()
            reply_to = reply_part.message_id if reply_part else None
        sent_at = datetime.fromtimestamp(int(message.get("date") or time.time()), tz=ufa_now().tzinfo)
        logical = CommunityMessage(topic_id=topic.id, author_id=author.id, app_user_id=linked_user.id if linked_user else None, reply_to_message_id=reply_to, source="telegram", telegram_media_group_id=media_group_id, text=raw_text, delivery_status="sent", sent_at=sent_at)
        db.add(logical); await db.flush()
    elif raw_text and not logical.text: logical.text = raw_text
    photo_sizes = message.get("photo") if isinstance(message.get("photo"), list) else []
    document = message.get("document") if isinstance(message.get("document"), dict) else None
    file_payload = max([item for item in photo_sizes if isinstance(item, dict)], key=lambda item: int(item.get("file_size") or 0), default=None) if photo_sizes else document
    attachment: CommunityAttachment | None = None
    file_id = ""
    if file_payload:
        file_id = str(file_payload.get("file_id") or "")
        original = _safe_filename(document.get("file_name") if document else None, f"photo-{telegram_message_id}.jpg" if photo_sizes else f"file-{telegram_message_id}")
        mime_type = str((document or {}).get("mime_type") or ("image/jpeg" if photo_sizes else "application/octet-stream"))
        attachment = CommunityAttachment(message_id=logical.id, kind="image" if photo_sizes else "document", original_filename=original, filename=f"telegram-{telegram_message_id}", mime_type=mime_type, size_bytes=int(file_payload.get("file_size") or 0), telegram_file_id=file_id, telegram_file_unique_id=str(file_payload.get("file_unique_id") or "") or None, telegram_message_id=telegram_message_id, status="telegram_only")
        db.add(attachment); await db.flush()
    unsupported_keys = ("voice", "video", "video_note", "sticker", "animation", "audio", "poll", "location", "contact")
    for key in unsupported_keys:
        if message.get(key) is not None: logical.unsupported_type = key; break
    db.add(CommunityTelegramPart(message_id=logical.id, telegram_chat_id=TELEGRAM_COMMUNITY_CHAT_ID, telegram_message_id=telegram_message_id))
    if not topic.last_message_at or logical.sent_at >= topic.last_message_at:
        topic.last_message_id = logical.id; topic.last_message_at = logical.sent_at
    # Make the mirrored message visible before slower Telegram media/profile downloads.
    await db.commit()
    await _upsert_author(db, kind=kind, telegram_peer_id=peer_id or -telegram_message_id, full_name=full_name, app_user_id=linked_user.id if linked_user else None, telegram_client=client)
    await db.commit()
    if attachment and file_id and attachment.size_bytes <= TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES:
        local_filename = f"{logical.id}-{uuid4().hex}"
        try:
            attachment.size_bytes = await client.download_file(file_id, COMMUNITY_ATTACHMENTS_DIR / local_filename, max_bytes=TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES)
            attachment.local_filename = local_filename; attachment.status = "ready"
            await db.commit()
        except (TelegramBotAPIError, TimeoutError, OSError):
            pass
    return {"ok": True, "community_message_id": logical.id}
