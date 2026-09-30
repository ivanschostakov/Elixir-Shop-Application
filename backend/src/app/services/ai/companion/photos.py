"""Progress photo records reference the existing private chat upload lifecycle."""
from fastapi import HTTPException
from sqlalchemy import select

from src.database.models import AIMessage, Attachment
from src.database.schemas.ai.attachment import AIAttachmentRead
from src.integrations.ai.enums import AttachmentType, MessageSender
from .mentor import DiaryEntryRead
from .schemas import StrictModel

RASTER_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif"}


class ProgressPhotoRead(DiaryEntryRead):
    photo_attachments: list[AIAttachmentRead]
    unavailable_photo_attachment_ids: list[int]


class ProgressPhotosRead(StrictModel):
    entries: list[ProgressPhotoRead]
    limit: int = 200
    may_have_more: bool = False


async def owned_photos(db, user_id, attachment_ids):
    if not attachment_ids:
        return {}
    rows = (await db.execute(select(Attachment).join(AIMessage).where(
        Attachment.id.in_(attachment_ids), Attachment.is_private.is_(True),
        Attachment.type == AttachmentType.IMAGE, Attachment.mime_type.in_(RASTER_MIME_TYPES),
        AIMessage.user_id == user_id, AIMessage.sender == MessageSender.USER,
        AIMessage.is_sensitive.is_(True),
    ))).scalars().all()
    # Read-time checks also prevent dangling references from exposing other or
    # public media after a source message/attachment is removed or changed.
    return {row.id: row for row in rows if row.path.is_file()}


async def validate_photo_attachments(db, user_id, attachment_ids):
    found = await owned_photos(db, user_id, attachment_ids)
    if len(found) != len(attachment_ids):
        raise HTTPException(422, "Выберите доступные личные фотографии из своих сообщений сопровождения")


async def serialize_entries(db, user_id, entries):
    from . import service
    ids = {photo_id for entry in entries if entry.kind == "progress_photo" and entry.user_id == user_id
        for photo_id in entry.data.get("photo_attachment_ids", [])}
    available = await owned_photos(db, user_id, ids)
    result = []
    for entry in entries:
        if entry.user_id != user_id:
            continue
        value = service.dump(entry)
        if entry.kind == "progress_photo":
            ids = entry.data.get("photo_attachment_ids", [])
            value["photo_attachments"] = [AIAttachmentRead.model_validate(available[i]).model_dump(mode="json") for i in ids if i in available]
            value["unavailable_photo_attachment_ids"] = [i for i in ids if i not in available]
        result.append(value)
    return result
