from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import CdekDoorAddress
from src.database.schemas import CdekDoorAddressCreate, CdekDoorAddressUpdate


async def create_cdek_door_address(session: AsyncSession, data: CdekDoorAddressCreate, *, commit: bool = True) -> CdekDoorAddress:
    address = CdekDoorAddress(**data.model_dump(), provider="CDEK")
    session.add(address)
    if commit:
        await session.commit()
    else:
        await session.flush()
    await session.refresh(address)
    return address


async def get_cdek_door_address_by_id(session: AsyncSession, address_id: int) -> CdekDoorAddress | None:
    return (await session.execute(select(CdekDoorAddress).where(CdekDoorAddress.id == address_id))).scalar_one_or_none()


async def get_cdek_door_addresses(session: AsyncSession, *, user_id: int | None = None, offset: int = 0, limit: int = 100) -> list[CdekDoorAddress]:
    stmt = select(CdekDoorAddress)
    if user_id is not None:
        stmt = stmt.where(CdekDoorAddress.user_id == user_id)
    stmt = stmt.order_by(CdekDoorAddress.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_cdek_door_address(session: AsyncSession, address: CdekDoorAddress, data: CdekDoorAddressUpdate, *, commit: bool = True) -> CdekDoorAddress:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(address, field, value)
    if commit:
        await session.commit()
    else:
        await session.flush()
    await session.refresh(address)
    return address


async def delete_cdek_door_address(session: AsyncSession, address: CdekDoorAddress) -> None:
    await session.delete(address)
    await session.commit()
