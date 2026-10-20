import hashlib
from pathlib import Path
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from config import TELEGRAM_COMMUNITY_CHAT_ID, ufa_now
from src.app.services.community import COMMUNITY_ATTACHMENTS_DIR, _is_telegram_app_reaction_notification, _safe_filename, _upsert_author
from src.database.crud.auth.user import get_user_by_telegram_user_id
from src.database.models import CommunityAttachment, CommunityMessage, CommunityTelegramPart, CommunityTopic
from .common import log
from .authors import _archived_app_author_name, _refresh_telethon_author_avatar, _telethon_author_snapshot, _telethon_message_text


async def _store_telethon_attachment(db: Any, *, client: Any, telegram_message: Any, logical: CommunityMessage,) -> None:
    telegram_message_id = int(getattr(telegram_message, "id", 0) or 0)
    is_photo = getattr(telegram_message, "photo", None) is not None
    unsupported_type = next((key for key in ("voice", "video", "video_note", "sticker", "gif", "audio", "poll", "geo", "contact") if getattr(telegram_message, key, None) is not None), None,)
    file_info = getattr(telegram_message, "file", None)
    is_audio = unsupported_type in {"voice", "audio"}
    is_document = getattr(telegram_message, "document", None) is not None and (unsupported_type is None or is_audio)
    if is_audio: logical.unsupported_type = None
    if not is_photo and not is_document:
        if unsupported_type: logical.unsupported_type = "location" if unsupported_type == "geo" else unsupported_type
        return

    size_bytes = int(getattr(file_info, "size", 0) or 0)
    fallback = f"photo-{telegram_message_id}.jpg" if is_photo else f"voice-{telegram_message_id}.ogg" if unsupported_type == "voice" else f"audio-{telegram_message_id}"
    original = _safe_filename(getattr(file_info, "name", None), fallback)
    fallback_mime_type = "image/jpeg" if is_photo else "audio/ogg" if unsupported_type == "voice" else "audio/mpeg" if unsupported_type == "audio" else "application/octet-stream"
    mime_type = str(getattr(file_info, "mime_type", "") or fallback_mime_type)
    # Never touch ``logical.attachments`` here. Newly-created logical messages
    # do not have that async relationship loaded, and attribute access would
    # attempt a synchronous lazy load (SQLAlchemy MissingGreenlet). An explicit
    # query is safe for both newly imported messages and repair passes.
    attachment = (await db.execute(select(CommunityAttachment).where(CommunityAttachment.message_id == logical.id, CommunityAttachment.telegram_message_id == telegram_message_id,))).scalar_one_or_none()
    if attachment is None:
        attachment = CommunityAttachment(message_id=logical.id, kind="image" if is_photo else "document", original_filename=original, filename=f"telegram-{telegram_message_id}", mime_type=mime_type, size_bytes=size_bytes, telegram_message_id=telegram_message_id, status="telegram_only",)
        db.add(attachment)
        await db.flush()
        logical.updated_at = ufa_now()
    if attachment.local_filename and attachment.status == "ready": return
    from config import TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES

    if not size_bytes or size_bytes > TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES: return
    suffix = Path(original).suffix[:16] or (".jpg" if is_photo else ".bin")
    local_filename = f"{logical.id}-{telegram_message_id}{suffix}"
    target = COMMUNITY_ATTACHMENTS_DIR / local_filename
    try:
        downloaded = await client.download_media(telegram_message, file=str(target))
        downloaded_path = Path(str(downloaded)) if downloaded else target
        if downloaded_path.exists() and downloaded_path.parent.resolve() == COMMUNITY_ATTACHMENTS_DIR.resolve():
            attachment.local_filename = downloaded_path.name
            attachment.size_bytes = downloaded_path.stat().st_size
            attachment.status = "ready"
            # Attachment rows are not part of the message change cursor. Bump
            # the logical parent so incremental app clients receive the newly
            # available media without waiting for a full refresh.
            logical.updated_at = ufa_now()
    except (OSError, TimeoutError):
        target.unlink(missing_ok=True)
        log.info("telethon history media download skipped message_id=%s", telegram_message_id)
    except Exception:
        target.unlink(missing_ok=True)
        log.exception("telethon history media download failed message_id=%s", telegram_message_id)


async def _upsert_telethon_message(db: Any, *, client: Any, topic: CommunityTopic, telegram_message: Any,) -> tuple[CommunityMessage | None, bool]:
    telegram_message_id = int(getattr(telegram_message, "id", 0) or 0)
    if telegram_message_id <= 0: return None, False
    existing_part = (await db.execute(select(CommunityTelegramPart).where(CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTelegramPart.telegram_message_id == telegram_message_id,).options(selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.attachments), selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.telegram_parts), selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.author),))).scalar_one_or_none()
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
        await _store_telethon_attachment(
            db,
            client=client,
            telegram_message=telegram_message,
            logical=logical,
        )
        if logical.author and logical.author.kind in {"user", "chat"}:
            sender = await telegram_message.get_sender()
            await _refresh_telethon_author_avatar(client, sender, logical.author)
        return logical, changed

    # Topic lifecycle/service records are represented by the topic model, not
    # as user-facing chat bubbles.
    if getattr(telegram_message, "action", None) is not None: return None, False

    sender = await telegram_message.get_sender()
    if bool(getattr(sender, "bot", False)) and _is_telegram_app_reaction_notification(_telethon_message_text(telegram_message)): return None, False
    archived_app_name = _archived_app_author_name(telegram_message)
    if archived_app_name:
        digest = hashlib.sha256(archived_app_name.casefold().encode("utf-8")).digest()
        kind = "app_archive"
        peer_id = -int.from_bytes(digest[:7], "big")
        full_name = archived_app_name
    else: kind, peer_id, full_name = _telethon_author_snapshot(sender, telegram_message_id)
    linked_user = await get_user_by_telegram_user_id(db, peer_id) if kind == "user" and peer_id > 0 else None
    author = await _upsert_author(db, kind=kind, telegram_peer_id=peer_id, full_name=full_name, app_user_id=linked_user.id if linked_user else None, refresh_avatar=False,)
    if not archived_app_name: await _refresh_telethon_author_avatar(client, sender, author)
    media_group_id = str(getattr(telegram_message, "grouped_id", "") or "") or None
    logical = None
    if media_group_id: logical = (await db.execute(select(CommunityMessage).where(CommunityMessage.topic_id == topic.id, CommunityMessage.telegram_media_group_id == media_group_id,).order_by(CommunityMessage.id.asc()).limit(1).options(selectinload(CommunityMessage.attachments)))).scalar_one_or_none()
    if logical is None:
        reply_to_message_id = None
        reply_to_telegram_id = int(getattr(telegram_message, "reply_to_msg_id", 0) or 0)
        if reply_to_telegram_id:
            reply_part = (await db.execute(select(CommunityTelegramPart).where(CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTelegramPart.telegram_message_id == reply_to_telegram_id,))).scalar_one_or_none()
            reply_to_message_id = reply_part.message_id if reply_part else None
        logical = CommunityMessage(topic_id=topic.id, author_id=author.id, app_user_id=linked_user.id if linked_user else None, reply_to_message_id=reply_to_message_id, source="telegram", telegram_media_group_id=media_group_id, text=_telethon_message_text(telegram_message), delivery_status="sent", sent_at=getattr(telegram_message, "date", None) or ufa_now(), edited_at=getattr(telegram_message, "edit_date", None),)
        db.add(logical)
        await db.flush()
    elif _telethon_message_text(telegram_message) and not logical.text: logical.text = _telethon_message_text(telegram_message)

    db.add(CommunityTelegramPart(message_id=logical.id, telegram_chat_id=TELEGRAM_COMMUNITY_CHAT_ID, telegram_message_id=telegram_message_id,))
    await db.flush()
    await _store_telethon_attachment(db, client=client, telegram_message=telegram_message, logical=logical)
    if not topic.last_message_at or logical.sent_at >= topic.last_message_at:
        topic.last_message_id = logical.id
        topic.last_message_at = logical.sent_at
    return logical, True
