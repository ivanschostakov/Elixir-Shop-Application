from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Variant
from src.database.schemas import VariantCreate, VariantUpdate


async def create_variant(session: AsyncSession, data: VariantCreate) -> Variant:
    variant = Variant(**data.model_dump())
    session.add(variant)
    await session.commit()
    await session.refresh(variant)
    return variant


async def get_variant_by_id(session: AsyncSession, variant_id: int) -> Variant | None:
    stmt = select(Variant).where(Variant.id == variant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_variant_by_system_id(session: AsyncSession, system_id: str) -> Variant | None:
    stmt = select(Variant).where(Variant.system_id == system_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_variants(session: AsyncSession, *, product_id: int | None = None, sku: str | None = None, q: str | None = None, offset: int = 0, limit: int = 100) -> list[Variant]:
    stmt = select(Variant)

    if product_id is not None: stmt = stmt.where(Variant.product_id == product_id)
    if sku is not None: stmt = stmt.where(Variant.sku == sku)
    if q: stmt = stmt.where(or_(Variant.name.ilike(f"%{q}%"), Variant.sku.ilike(f"%{q}%")))

    stmt = stmt.order_by(Variant.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_variant(session: AsyncSession, variant: Variant, data: VariantUpdate) -> Variant:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(variant, field, value)
    await session.commit()
    await session.refresh(variant)
    return variant


async def delete_variant(session: AsyncSession, variant: Variant) -> None:
    await session.delete(variant)
    await session.commit()
