from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Attachment
from src.database.schemas import AIAttachmentCreate, AIAttachmentUpdate
from src.integrations.ai.enums import AttachmentType


async def create_ai_attachment(session: AsyncSession, data: AIAttachmentCreate, *, commit: bool = True) -> Attachment:
    attachment = Attachment(**data.model_dump(exclude_none=True))
    session.add(attachment)
    await session.flush()

    if commit:
        await session.commit()
        await session.refresh(attachment)

    return attachment


async def get_ai_attachment_by_id(session: AsyncSession, attachment_id: int, message_id: int | None = None) -> Attachment | None:
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    if message_id is not None: stmt = stmt.where(Attachment.message_id == message_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_ai_attachments(session: AsyncSession, message_id: int | None = None, attachment_type: AttachmentType | None = None, offset: int = 0, limit: int = 100) -> list[Attachment]:
    stmt = select(Attachment).order_by(Attachment.id.asc()).offset(offset).limit(limit)
    if message_id is not None: stmt = stmt.where(Attachment.message_id == message_id)
    if attachment_type is not None: stmt = stmt.where(Attachment.type == attachment_type)
    return list((await session.execute(stmt)).scalars().all())


async def update_ai_attachment(session: AsyncSession, attachment: Attachment, data: AIAttachmentUpdate, commit: bool = True) -> Attachment:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(attachment, field, value)
    await session.flush()

    if commit:
        await session.commit()
        await session.refresh(attachment)

    return attachment


async def delete_ai_attachment(session: AsyncSession, attachment: Attachment, *, commit: bool = True) -> None:
    await session.delete(attachment)
    await session.flush()

    if commit: await session.commit()
