from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import YandexPickupAddress
from src.database.schemas import YandexPickupAddressCreate, YandexPickupAddressUpdate


async def create_yandex_pickup_address(session: AsyncSession, data: YandexPickupAddressCreate, *, commit: bool = True) -> YandexPickupAddress:
    address = YandexPickupAddress(**data.model_dump(), provider="YANDEX")
    session.add(address)
    if commit: await session.commit()
    else: await session.flush()
    await session.refresh(address)
    return address


async def get_yandex_pickup_address_by_id(session: AsyncSession, address_id: int) -> YandexPickupAddress | None:
    return (await session.execute(select(YandexPickupAddress).where(YandexPickupAddress.id == address_id))).scalar_one_or_none()


async def get_yandex_pickup_addresses(session: AsyncSession, *, user_id: int | None = None, offset: int = 0, limit: int = 100) -> list[YandexPickupAddress]:
    stmt = select(YandexPickupAddress)
    if user_id is not None: stmt = stmt.where(YandexPickupAddress.user_id == user_id)
    stmt = stmt.order_by(YandexPickupAddress.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_yandex_pickup_address(session: AsyncSession, address: YandexPickupAddress, data: YandexPickupAddressUpdate, *, commit: bool = True) -> YandexPickupAddress:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(address, field, value)
    if commit: await session.commit()
    else: await session.flush()
    await session.refresh(address)
    return address


async def delete_yandex_pickup_address(session: AsyncSession, address: YandexPickupAddress) -> None:
    await session.delete(address)
    await session.commit()
