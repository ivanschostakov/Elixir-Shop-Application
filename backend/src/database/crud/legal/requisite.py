from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Requisite
from src.database.schemas import RequisiteCreate, RequisiteUpdate


async def create_requisite(session: AsyncSession, data: RequisiteCreate) -> Requisite:
    requisite = Requisite(**data.model_dump())
    session.add(requisite)
    await session.commit()
    await session.refresh(requisite)
    return requisite


async def get_requisite_by_id(session: AsyncSession, requisite_id: int) -> Requisite | None:
    stmt = select(Requisite).where(Requisite.id == requisite_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_requisites(session: AsyncSession) -> list[Requisite]:
    stmt = select(Requisite).order_by(Requisite.created_at.asc(), Requisite.id.asc())
    return list((await session.execute(stmt)).scalars().all())


async def update_requisite(session: AsyncSession, requisite: Requisite, data: RequisiteUpdate) -> Requisite:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(requisite, field, value)
    await session.commit()
    await session.refresh(requisite)
    return requisite


async def delete_requisite(session: AsyncSession, requisite: Requisite) -> None:
    await session.delete(requisite)
    await session.commit()
