import mimetypes
from datetime import datetime
from uuid import uuid4
from fastapi import HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from config import TELEGRAM_COMMUNITY_CHAT_ID, TELEGRAM_COMMUNITY_MAX_ATTACHMENT_BYTES, TELEGRAM_COMMUNITY_MAX_ATTACHMENTS, TELEGRAM_COMMUNITY_MAX_TOTAL_ATTACHMENT_BYTES, ufa_now
from src.database.schemas.community import CommunityMessageRead
from src.app.services.upload_limits import read_upload_file_limited
from src.database.models import CommunityAttachment, CommunityMessage, CommunityNotificationEvent, CommunityTelegramPart, CommunityTopic, User
from src.integrations.telegram import TelegramBotAPIError, TelegramBotClient, get_telegram_bot_client
from .common import COMMUNITY_ATTACHMENTS_DIR
from .media import _safe_filename
from .access import require_community_access
from .reading import _message_options, serialize_community_message
from .blocks import blocked_community_author_ids
from .authors import _upsert_author
from .telegram_helpers import _delete_telegram_message_ids, _telegram_app_header, _telegram_author_entities


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
        return serialize_community_message(existing, request=request, user_id=user.id, blocked_author_ids=await blocked_community_author_ids(db, user.id))
    reply_to = await db.get(CommunityMessage, reply_to_message_id) if reply_to_message_id else None
    if reply_to_message_id and (reply_to is None or reply_to.topic_id != topic_id): raise HTTPException(status_code=422, detail="Reply target is not in this topic")
    if reply_to and (reply_to.deleted_at or reply_to.author_id in await blocked_community_author_ids(db, user.id)): raise HTTPException(422, "Reply target is unavailable")
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
    db.add(CommunityNotificationEvent(message_id=message.id))
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
    return serialize_community_message(message, request=request, user_id=user.id, blocked_author_ids=await blocked_community_author_ids(db, user.id))


async def _refresh_topic_last_message(db: AsyncSession, topic: CommunityTopic) -> None:
    latest = (await db.execute(select(CommunityMessage).where(CommunityMessage.topic_id == topic.id, CommunityMessage.deleted_at.is_(None)).order_by(CommunityMessage.sent_at.desc(), CommunityMessage.id.desc()).limit(1))).scalar_one_or_none()
    topic.last_message_id = latest.id if latest else None
    topic.last_message_at = latest.sent_at if latest else None


def _soft_delete_message(message: CommunityMessage, *, deleted_at: datetime | None = None) -> None:
    when = deleted_at or ufa_now()
    message.deleted_at = when
    message.text = ""
    message.unsupported_type = None
    for attachment in message.attachments:
        if attachment.local_filename: (COMMUNITY_ATTACHMENTS_DIR / attachment.local_filename).unlink(missing_ok=True)
        attachment.local_filename = None
        attachment.status = "deleted"


async def edit_community_message(db: AsyncSession, *, user: User, request: Request, topic_id: int, message_id: int, text: str, telegram_client: TelegramBotClient | None = None,) -> CommunityMessageRead:
    await require_community_access(user)
    normalized_text = text.strip()
    if not normalized_text: raise HTTPException(status_code=422, detail="Message text must not be empty")
    message = (await db.execute(select(CommunityMessage).where(CommunityMessage.id == message_id, CommunityMessage.topic_id == topic_id).options(*_message_options(), selectinload(CommunityMessage.topic)))).scalar_one_or_none()
    if message is None: raise HTTPException(status_code=404, detail="Community message not found")
    if message.app_user_id != user.id or message.source != "app": raise HTTPException(status_code=403, detail="You can edit only your own app messages")
    if message.deleted_at: raise HTTPException(status_code=409, detail="Deleted messages cannot be edited")

    edited_at = ufa_now()
    if message.delivery_status in {"queued", "failed"} and not message.telegram_parts:
        message.text = normalized_text
        message.edited_at = edited_at
        await db.commit()
    else:
        author_name, header = _telegram_app_header(message)
        rendered = f"{header}\n\n{normalized_text}"
        active_parts = [part for part in message.telegram_parts if part.deleted_at is None]
        attachment_part_ids = {int(attachment.telegram_message_id) for attachment in message.attachments if attachment.telegram_message_id}
        text_parts = [part for part in active_parts if part.telegram_message_id not in attachment_part_ids]
        client = telegram_client or get_telegram_bot_client()
        try:
            if text_parts:
                if len(rendered) > 4096: raise HTTPException(status_code=422, detail="Edited message is too long for Telegram")
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
                    for part in text_parts[1:]: part.deleted_at = edited_at
            elif active_parts and attachment_part_ids:
                if len(rendered) > 1024: raise HTTPException(status_code=422, detail="Edited attachment caption is too long for Telegram")
                target = next((part for part in active_parts if part.telegram_message_id in attachment_part_ids), active_parts[0],)
                await client.call(
                    "editMessageCaption",
                    data={
                        "chat_id": TELEGRAM_COMMUNITY_CHAT_ID,
                        "message_id": target.telegram_message_id,
                        "caption": rendered,
                        "caption_entities": _telegram_author_entities(rendered, author_name),
                    },
                )
            else: raise HTTPException(status_code=409, detail="This message has not been delivered to Telegram yet")
        except (TelegramBotAPIError, TimeoutError, OSError) as exc: raise HTTPException(status_code=502, detail="Telegram could not edit this message") from exc
        message.text = normalized_text
        message.edited_at = edited_at
        await db.commit()

    message = (await db.execute(select(CommunityMessage).where(CommunityMessage.id == message_id).options(*_message_options(), selectinload(CommunityMessage.topic)))).scalar_one()
    return serialize_community_message(message, request=request, user_id=user.id, blocked_author_ids=await blocked_community_author_ids(db, user.id))


async def delete_community_message(db: AsyncSession, *, user: User, topic_id: int, message_id: int, telegram_client: TelegramBotClient | None = None,) -> None:
    await require_community_access(user)
    message = (await db.execute(select(CommunityMessage).where(CommunityMessage.id == message_id, CommunityMessage.topic_id == topic_id).options(selectinload(CommunityMessage.attachments), selectinload(CommunityMessage.telegram_parts), selectinload(CommunityMessage.reactions), selectinload(CommunityMessage.topic),))).scalar_one_or_none()
    if message is None: raise HTTPException(status_code=404, detail="Community message not found")
    if message.app_user_id != user.id or message.source != "app": raise HTTPException(status_code=403, detail="You can delete only your own app messages")
    if message.deleted_at: return
    active_parts = [part for part in message.telegram_parts if part.deleted_at is None]
    telegram_message_ids = [part.telegram_message_id for part in active_parts]
    telegram_message_ids.extend(reaction.telegram_message_id for reaction in message.reactions if reaction.telegram_message_id)
    if telegram_message_ids:
        try:
            await _delete_telegram_message_ids(
                telegram_client or get_telegram_bot_client(),
                chat_id=TELEGRAM_COMMUNITY_CHAT_ID,
                message_ids=telegram_message_ids,
            )
        except (TelegramBotAPIError, TimeoutError, OSError) as exc: raise HTTPException(status_code=502, detail="Telegram could not delete this message") from exc
    deleted_at = ufa_now()
    for part in active_parts: part.deleted_at = deleted_at
    for reaction in message.reactions:
        reaction.telegram_chat_id = None
        reaction.telegram_message_id = None
    _soft_delete_message(message, deleted_at=deleted_at)
    await _refresh_topic_last_message(db, message.topic)
    await db.commit()


async def mark_community_telegram_messages_deleted(db: AsyncSession, telegram_message_ids: list[int], *, deleted_at: datetime | None = None,) -> int:
    normalized_ids = sorted({int(message_id) for message_id in telegram_message_ids if int(message_id) > 0})
    if not normalized_ids: return 0
    parts = list((await db.execute(select(CommunityTelegramPart).where(CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTelegramPart.telegram_message_id.in_(normalized_ids),).options(selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.telegram_parts), selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.attachments), selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.topic),))).scalars().all())
    when = deleted_at or ufa_now()
    affected_messages: dict[int, CommunityMessage] = {}
    for part in parts:
        part.deleted_at = when
        affected_messages[part.message_id] = part.message
        for attachment in part.message.attachments:
            if attachment.telegram_message_id == part.telegram_message_id:
                if attachment.local_filename: (COMMUNITY_ATTACHMENTS_DIR / attachment.local_filename).unlink(missing_ok=True)
                attachment.local_filename = None
                attachment.status = "deleted"
    affected_topics: dict[int, CommunityTopic] = {}
    for message in affected_messages.values():
        if all(part.deleted_at is not None for part in message.telegram_parts):
            _soft_delete_message(message, deleted_at=when)
            affected_topics[message.topic.id] = message.topic
    for topic in affected_topics.values(): await _refresh_topic_last_message(db, topic)
    return len(parts)
