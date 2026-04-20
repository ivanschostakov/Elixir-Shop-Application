from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import YandexDoorAddress
from src.database.schemas import YandexDoorAddressCreate, YandexDoorAddressUpdate


async def create_yandex_door_address(session: AsyncSession, data: YandexDoorAddressCreate, *, commit: bool = True) -> YandexDoorAddress:
    address = YandexDoorAddress(**data.model_dump(), provider="YANDEX")
    session.add(address)
    if commit: await session.commit()
    else: await session.flush()
    await session.refresh(address)
    return address


async def get_yandex_door_address_by_id(session: AsyncSession, address_id: int) -> YandexDoorAddress | None:
    return (await session.execute(select(YandexDoorAddress).where(YandexDoorAddress.id == address_id))).scalar_one_or_none()


async def get_yandex_door_addresses(session: AsyncSession, *, user_id: int | None = None, offset: int = 0, limit: int = 100) -> list[YandexDoorAddress]:
    stmt = select(YandexDoorAddress)
    if user_id is not None: stmt = stmt.where(YandexDoorAddress.user_id == user_id)
    stmt = stmt.order_by(YandexDoorAddress.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_yandex_door_address(session: AsyncSession, address: YandexDoorAddress, data: YandexDoorAddressUpdate, *, commit: bool = True) -> YandexDoorAddress:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(address, field, value)
    if commit: await session.commit()
    else: await session.flush()
    await session.refresh(address)
    return address


async def delete_yandex_door_address(session: AsyncSession, address: YandexDoorAddress) -> None:
    await session.delete(address)
    await session.commit()
