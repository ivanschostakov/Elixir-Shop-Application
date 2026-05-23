from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ProductCategory
from src.database.schemas import ProductCategoryCreate, ProductCategoryUpdate


async def create_product_category(session: AsyncSession, data: ProductCategoryCreate) -> ProductCategory:
    product_category = ProductCategory(**data.model_dump())
    session.add(product_category)
    await session.commit()
    await session.refresh(product_category)
    return product_category


async def get_product_category_by_id(session: AsyncSession, product_category_id: int, *, include_archived: bool = False) -> ProductCategory | None:
    stmt = select(ProductCategory).where(ProductCategory.id == product_category_id)
    if not include_archived: stmt = stmt.where(ProductCategory.archived.is_(False))
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_product_category_by_name(session: AsyncSession, name: str, *, include_archived: bool = False) -> ProductCategory | None:
    stmt = select(ProductCategory).where(ProductCategory.name == name)
    if not include_archived: stmt = stmt.where(ProductCategory.archived.is_(False))
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_product_categories(session: AsyncSession, *, q: str | None = None, name: str | None = None, offset: int = 0, limit: int = 100, sort: str | None = None, include_archived: bool = False) -> list[ProductCategory]:
    stmt = select(ProductCategory)
    if not include_archived: stmt = stmt.where(ProductCategory.archived.is_(False))
    if name is not None: stmt = stmt.where(ProductCategory.name == name)
    if q: stmt = stmt.where(or_(ProductCategory.name.ilike(f"%{q}%"), ProductCategory.description.ilike(f"%{q}%")))

    sort_map = {
        "newest": (ProductCategory.created_at.desc(), ProductCategory.id.desc()),
        "name_asc": (func.lower(ProductCategory.name).asc(), ProductCategory.id.asc()),
        "name_desc": (func.lower(ProductCategory.name).desc(), ProductCategory.id.asc()),
    }
    if sort in sort_map: stmt = stmt.order_by(*sort_map[sort])
    else: stmt = stmt.order_by(func.lower(ProductCategory.name).asc(), ProductCategory.id.asc())
    stmt = stmt.offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_product_category(session: AsyncSession, product_category: ProductCategory, data: ProductCategoryUpdate) -> ProductCategory:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(product_category, field, value)
    await session.commit()
    await session.refresh(product_category)
    return product_category


async def delete_product_category(session: AsyncSession, product_category: ProductCategory) -> None:
    await session.delete(product_category)
    await session.commit()
