from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Product, ProductByCategory, ProductCategory
from src.database.schemas import ProductByCategoryCreate, ProductByCategoryUpdate


async def create_product_by_category(session: AsyncSession, data: ProductByCategoryCreate) -> ProductByCategory:
    product_by_category = ProductByCategory(**data.model_dump())
    session.add(product_by_category)
    await session.commit()
    await session.refresh(product_by_category)
    return product_by_category


async def get_product_by_category_by_id(session: AsyncSession, product_by_category_id: int) -> ProductByCategory | None:
    stmt = select(ProductByCategory).where(ProductByCategory.id == product_by_category_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_product_by_category_by_product_and_category(session: AsyncSession, product_id: int, category_id: int) -> ProductByCategory | None:
    stmt = select(ProductByCategory).where(ProductByCategory.product_id == product_id, ProductByCategory.category_id == category_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_product_by_category_links(session: AsyncSession, *, product_id: int | None = None, category_id: int | None = None, offset: int = 0, limit: int = 100) -> list[ProductByCategory]:
    stmt = select(ProductByCategory)

    if product_id is not None: stmt = stmt.where(ProductByCategory.product_id == product_id)
    if category_id is not None: stmt = stmt.where(ProductByCategory.category_id == category_id)

    stmt = stmt.order_by(ProductByCategory.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_products_for_category(
    session: AsyncSession,
    category_id: int,
    *,
    product_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    include_archived: bool = False,
) -> list[Product]:
    stmt = (
        select(Product)
        .join(ProductByCategory, ProductByCategory.product_id == Product.id)
        .where(ProductByCategory.category_id == category_id)
    )

    if not include_archived:
        stmt = stmt.where(Product.archived.is_(False))
    if product_id is not None: stmt = stmt.where(ProductByCategory.product_id == product_id)
    stmt = stmt.order_by(ProductByCategory.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_categories_for_product(session: AsyncSession, product_id: int, *, category_id: int | None = None, offset: int = 0, limit: int = 100) -> list[ProductCategory]:
    stmt = (
        select(ProductCategory)
        .join(ProductByCategory, ProductByCategory.category_id == ProductCategory.id)
        .where(ProductByCategory.product_id == product_id)
    )

    if category_id is not None: stmt = stmt.where(ProductByCategory.category_id == category_id)
    stmt = stmt.order_by(ProductByCategory.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_product_by_category(session: AsyncSession, product_by_category: ProductByCategory, data: ProductByCategoryUpdate) -> ProductByCategory:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(product_by_category, field, value)
    await session.commit()
    await session.refresh(product_by_category)
    return product_by_category


async def delete_product_by_category(session: AsyncSession, product_by_category: ProductByCategory) -> None:
    await session.delete(product_by_category)
    await session.commit()
