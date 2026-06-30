from decimal import Decimal
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services.referrals.calculations import quantize_money
from src.database.models import Product, ProductByCategory, ProductCategory
from src.normalize import optional_str

NON_DISCOUNTABLE_CATEGORY_NAMES = frozenset(("сопутствующие товары",))


def is_non_discountable_category_name(name: str | None) -> bool:
    normalized = optional_str(name)
    return bool(normalized and normalized.casefold() in NON_DISCOUNTABLE_CATEGORY_NAMES)


def product_is_discountable(product: Product | None) -> bool:
    if product is None:
        return True

    for link in getattr(product, "products_by_category", ()) or ():
        if is_non_discountable_category_name(getattr(getattr(link, "category", None), "name", None)):
            return False
    return True


async def get_non_discountable_product_ids(db: AsyncSession, product_ids: Iterable[int]) -> set[int]:
    ids = {int(product_id) for product_id in product_ids if product_id is not None}
    if not ids:
        return set()

    stmt = (
        select(ProductByCategory.product_id)
        .join(ProductCategory, ProductCategory.id == ProductByCategory.category_id)
        .where(
            ProductByCategory.product_id.in_(ids),
            func.lower(ProductCategory.name).in_(NON_DISCOUNTABLE_CATEGORY_NAMES),
        )
    )
    return {int(product_id) for product_id in (await db.execute(stmt)).scalars().all()}


async def discountable_subtotal_for_lines(db: AsyncSession, lines: Iterable[tuple[int, Decimal | int | float | str | None]]) -> Decimal:
    rows = [(int(product_id), quantize_money(line_total)) for product_id, line_total in lines]
    if not rows:
        return Decimal("0.00")

    excluded_product_ids = await get_non_discountable_product_ids(db, (product_id for product_id, _ in rows))
    return quantize_money(sum((line_total for product_id, line_total in rows if product_id not in excluded_product_ids), Decimal("0.00")))
