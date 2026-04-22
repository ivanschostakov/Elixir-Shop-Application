from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import DeliveryAddress
from src.database.schemas import DeliveryAddressCreate


async def create_delivery_address(
    session: AsyncSession,
    data: DeliveryAddressCreate,
    *,
    commit: bool = True,
) -> DeliveryAddress:
    address = DeliveryAddress(**data.model_dump())
    session.add(address)
    await session.flush()

    if commit:
        await session.commit()
        await session.refresh(address)

    return address


async def get_delivery_address_by_id(session: AsyncSession, address_id: int) -> DeliveryAddress | None:
    stmt = select(DeliveryAddress).where(DeliveryAddress.id == address_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_delivery_address_by_fields(
    session: AsyncSession,
    *,
    user_id: int,
    mode: str,
    provider: str,
    country_code: str,
    full_address: str,
    details: str | None,
    city: str | None,
    postal_code: str | None,
    provider_reference: str | None,
) -> DeliveryAddress | None:
    stmt = (
        select(DeliveryAddress)
        .where(DeliveryAddress.user_id == user_id)
        .where(DeliveryAddress.mode == mode)
        .where(DeliveryAddress.provider == provider)
        .where(DeliveryAddress.country_code == country_code)
        .where(DeliveryAddress.full_address == full_address)
        .limit(1)
    )

    optional_fields = (
        (DeliveryAddress.details, details),
        (DeliveryAddress.city, city),
        (DeliveryAddress.postal_code, postal_code),
        (DeliveryAddress.provider_reference, provider_reference),
    )
    for column, value in optional_fields:
        stmt = stmt.where(column.is_(None) if value is None else column == value)

    return (await session.execute(stmt)).scalar_one_or_none()


async def get_delivery_addresses(
    session: AsyncSession,
    *,
    user_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[DeliveryAddress]:
    stmt = select(DeliveryAddress)
    if user_id is not None:
        stmt = stmt.where(DeliveryAddress.user_id == user_id)

    stmt = stmt.order_by(DeliveryAddress.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())
