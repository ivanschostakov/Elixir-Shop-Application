from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import CdekPickupAddress
from src.database.schemas import CdekPickupAddressCreate, CdekPickupAddressUpdate


async def create_cdek_pickup_address(session: AsyncSession, data: CdekPickupAddressCreate, *, commit: bool = True) -> CdekPickupAddress:
    address = CdekPickupAddress(**data.model_dump(), provider="CDEK")
    session.add(address)
    if commit: await session.commit()
    else: await session.flush()
    await session.refresh(address)
    return address


async def get_cdek_pickup_address_by_id(session: AsyncSession, address_id: int) -> CdekPickupAddress | None:
    return (await session.execute(select(CdekPickupAddress).where(CdekPickupAddress.id == address_id))).scalar_one_or_none()


async def get_cdek_pickup_addresses(session: AsyncSession, *, user_id: int | None = None, offset: int = 0, limit: int = 100) -> list[CdekPickupAddress]:
    stmt = select(CdekPickupAddress)
    if user_id is not None: stmt = stmt.where(CdekPickupAddress.user_id == user_id)
    stmt = stmt.order_by(CdekPickupAddress.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_cdek_pickup_address(session: AsyncSession, address: CdekPickupAddress, data: CdekPickupAddressUpdate, *, commit: bool = True) -> CdekPickupAddress:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(address, field, value)
    if commit: await session.commit()
    else: await session.flush()
    await session.refresh(address)
    return address


async def delete_cdek_pickup_address(session: AsyncSession, address: CdekPickupAddress) -> None:
    await session.delete(address)
    await session.commit()
