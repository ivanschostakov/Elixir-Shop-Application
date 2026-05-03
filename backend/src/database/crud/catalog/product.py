from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.product_media import resolve_product_image_path
from src.database.search import build_search_query_variants

from src.database.models import Product, ProductByCategory, Variant
from src.database.schemas import ProductCreate, ProductUpdate


def _in_stock_product_clause():
    return Product.in_stock.is_(True)


def _compact_sku_search_token(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def _normalized_product_sku_expression():
    expr = func.lower(Product.sku)
    for token in ("-", "_", " ", ".", "/", "\\"):
        expr = func.replace(expr, token, "")
    return expr


def _has_product_image(*, product_id: int | None = None, system_id) -> bool:
    return resolve_product_image_path(product_id=product_id, system_id=system_id) is not None


def _apply_image_priority_guard(payload: dict, *, product_id: int | None = None, system_id) -> dict:
    if not _has_product_image(product_id=product_id, system_id=payload.get("system_id", system_id)): payload["priority"] = 0
    return payload


async def create_product(session: AsyncSession, data: ProductCreate) -> Product:
    product = Product(**_apply_image_priority_guard(data.model_dump(), system_id=data.system_id))
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def get_product_by_id(session: AsyncSession, product_id: int, *, include_out_of_stock: bool = True) -> Product | None:
    stmt = select(Product).options(selectinload(Product.variants)).where(Product.id == product_id)
    if not include_out_of_stock:
        stmt = stmt.where(_in_stock_product_clause())
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_product_by_system_id(session: AsyncSession, system_id: str) -> Product | None:
    return (await session.execute(select(Product).where(Product.system_id == system_id))).scalar_one_or_none()


async def get_product_by_sku(session: AsyncSession, sku: str) -> Product | None:
    return (await session.execute(select(Product).where(Product.sku == sku))).scalar_one_or_none()


async def get_products(session: AsyncSession, *, q: str | None = None, sku: str | None = None, min_priority: int | None = None, category_id: int | None = None, offset: int = 0, limit: int = 100, sort: str = None) -> list[Product]:
    stmt = select(Product).options(selectinload(Product.variants))
    if category_id is not None:
        stmt = stmt.join(ProductByCategory, ProductByCategory.product_id == Product.id).where(ProductByCategory.category_id == category_id)
    if sku is not None: stmt = stmt.where(Product.sku == sku)
    if min_priority is not None: stmt = stmt.where(Product.priority >= min_priority)
    if q:
        query_variants = build_search_query_variants(q)
        predicates = []
        compact_sku_variants: set[str] = set()
        normalized_product_sku = _normalized_product_sku_expression()
        for variant in query_variants:
            pattern = f"%{variant}%"
            predicates.extend(
                [
                    Product.name.ilike(pattern),
                    Product.sku.ilike(pattern),
                ]
            )
            compact_sku = _compact_sku_search_token(variant)
            if compact_sku and compact_sku not in compact_sku_variants:
                compact_sku_variants.add(compact_sku)
                predicates.append(normalized_product_sku.ilike(f"%{compact_sku}%"))
        if predicates:
            stmt = stmt.where(or_(*predicates))

    min_variant_price = select(func.min(Variant.price)).where(Variant.product_id == Product.id).correlate(Product).scalar_subquery()
    max_variant_price = select(func.max(Variant.price)).where(Variant.product_id == Product.id).correlate(Product).scalar_subquery()
    in_stock_first = Product.in_stock.desc()
    sort_map = {
        "newest": (in_stock_first, Product.created_at.desc(), Product.id.desc()),
        "name_asc": (in_stock_first, func.lower(Product.name).asc(), Product.id.asc()),
        "name_desc": (in_stock_first, func.lower(Product.name).desc(), Product.id.asc()),
        "price_asc": (in_stock_first, min_variant_price.is_(None), min_variant_price.asc(), Product.id.asc()),
        "price_desc": (in_stock_first, max_variant_price.is_(None), max_variant_price.desc(), Product.id.asc()),
    }
    if sort in sort_map: stmt = stmt.order_by(*sort_map[sort])
    else: stmt = stmt.order_by(in_stock_first, Product.priority.desc(), Product.id.desc())

    stmt = stmt.offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_similar_products(
    session: AsyncSession,
    *,
    product_id: int,
    offset: int = 0,
    limit: int = 6,
) -> list[Product]:
    category_ids_stmt = select(ProductByCategory.category_id).where(ProductByCategory.product_id == product_id)
    category_ids = [int(category_id) for category_id in (await session.execute(category_ids_stmt)).scalars().all()]
    if not category_ids:
        return []

    shared_category_counts = (
        select(
            ProductByCategory.product_id.label("product_id"),
            func.count(distinct(ProductByCategory.category_id)).label("shared_category_count"),
        )
        .where(
            ProductByCategory.category_id.in_(category_ids),
            ProductByCategory.product_id != product_id,
        )
        .group_by(ProductByCategory.product_id)
        .subquery()
    )

    stmt = (
        select(Product)
        .options(selectinload(Product.variants))
        .join(shared_category_counts, shared_category_counts.c.product_id == Product.id)
        .where(_in_stock_product_clause())
        .order_by(
            shared_category_counts.c.shared_category_count.desc(),
            Product.created_at.desc(),
            Product.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_priority_products(session: AsyncSession, *, min_priority: int = 1, offset: int = 0, limit: int = 100) -> list[Product]:
    stmt = (
        select(Product)
        .options(selectinload(Product.variants))
        .where(_in_stock_product_clause(), Product.priority >= min_priority)
        .order_by(Product.priority.desc(), Product.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def update_product(session: AsyncSession, product: Product, data: ProductUpdate) -> Product:
    for field, value in _apply_image_priority_guard(data.model_dump(exclude_unset=True), product_id=product.id, system_id=product.system_id).items(): setattr(product, field, value)
    await session.commit()
    await session.refresh(product)
    return product


async def delete_product(session: AsyncSession, product: Product) -> None:
    await session.delete(product)
    await session.commit()
