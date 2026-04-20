from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import FavouredProduct, Product
from src.database.schemas import FavouredProductCreate, FavouredProductUpdate


async def create_favoured_product(session: AsyncSession, data: FavouredProductCreate) -> FavouredProduct:
    favoured_product = FavouredProduct(**data.model_dump())
    session.add(favoured_product)
    await session.commit()
    await session.refresh(favoured_product)
    return favoured_product


async def get_favoured_product_by_id(session: AsyncSession, favoured_product_id: int) -> FavouredProduct | None:
    return (await session.execute(select(FavouredProduct).where(FavouredProduct.id == favoured_product_id))).scalar_one_or_none()


async def get_favoured_product_by_user_and_product(session: AsyncSession, user_id: int, product_id: int) -> FavouredProduct | None:
    stmt = select(FavouredProduct).where(FavouredProduct.user_id == user_id, FavouredProduct.product_id == product_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_favoured_products(session: AsyncSession, *, user_id: int | None = None, product_id: int | None = None, offset: int = 0, limit: int = 100) -> list[FavouredProduct]:
    stmt = select(FavouredProduct)
    if user_id is not None: stmt = stmt.where(FavouredProduct.user_id == user_id)
    if product_id is not None: stmt = stmt.where(FavouredProduct.product_id == product_id)
    stmt = stmt.order_by(FavouredProduct.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_favourite_products_for_user(session: AsyncSession, user_id: int, *, product_id: int | None = None, offset: int = 0, limit: int = 100) -> list[Product]:
    stmt = select(Product).join(FavouredProduct, FavouredProduct.product_id == Product.id).where(FavouredProduct.user_id == user_id)
    if product_id is not None: stmt = stmt.where(FavouredProduct.product_id == product_id)
    stmt = stmt.order_by(Product.in_stock.desc(), FavouredProduct.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_favoured_product(session: AsyncSession, favoured_product: FavouredProduct, data: FavouredProductUpdate) -> FavouredProduct:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(favoured_product, field, value)
    await session.commit()
    await session.refresh(favoured_product)
    return favoured_product


async def delete_favoured_product(session: AsyncSession, favoured_product: FavouredProduct) -> None:
    await session.delete(favoured_product)
    await session.commit()
