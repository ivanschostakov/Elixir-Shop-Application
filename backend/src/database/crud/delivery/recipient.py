from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import DeliveryRecipient
from src.database.schemas import DeliveryRecipientCreate


async def create_delivery_recipient(
    session: AsyncSession,
    data: DeliveryRecipientCreate,
    *,
    commit: bool = True,
) -> DeliveryRecipient:
    recipient = DeliveryRecipient(**data.model_dump())
    session.add(recipient)
    await session.flush()

    if commit:
        await session.commit()
        await session.refresh(recipient)

    return recipient


async def get_delivery_recipient_by_id(
    session: AsyncSession,
    recipient_id: int,
    *,
    user_id: int | None = None,
) -> DeliveryRecipient | None:
    stmt = select(DeliveryRecipient).where(DeliveryRecipient.id == recipient_id)
    if user_id is not None:
        stmt = stmt.where(DeliveryRecipient.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_delivery_recipient_by_fields(
    session: AsyncSession,
    *,
    user_id: int,
    name: str,
    surname: str,
    phone: str,
    email: str,
) -> DeliveryRecipient | None:
    stmt = (
        select(DeliveryRecipient)
        .where(DeliveryRecipient.user_id == user_id)
        .where(func.lower(DeliveryRecipient.name) == name.lower())
        .where(func.lower(DeliveryRecipient.surname) == surname.lower())
        .where(DeliveryRecipient.phone == phone)
        .where(DeliveryRecipient.email == email)
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_delivery_recipients(session: AsyncSession, user_id: int, *, limit: int = 20) -> list[DeliveryRecipient]:
    stmt = (
        select(DeliveryRecipient)
        .where(DeliveryRecipient.user_id == user_id)
        .order_by(DeliveryRecipient.updated_at.desc(), DeliveryRecipient.id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
