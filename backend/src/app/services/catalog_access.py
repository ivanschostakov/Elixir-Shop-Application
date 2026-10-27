"""Configured customer catalog visibility; None means the full catalog."""
from collections.abc import Iterable
import config
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Product, ProductByCategory

CatalogScope = tuple[int, ...] | None


def customer_category_scope(user_id: int | None) -> CatalogScope:
    if config.CATALOG_ACCESSORY_CATEGORY_ID <= 0:
        return None
    restricted = (
        config.CATALOG_GUEST_ACCESSORIES_ONLY if user_id is None
        else str(user_id) in config.CATALOG_ACCESSORY_ONLY_USER_IDS
    )
    return (config.CATALOG_ACCESSORY_CATEGORY_ID,) if restricted else None


def purchase_category_scope(user_id: int | None, *, client_platform: str | None = None) -> CatalogScope:
    if config.APPLE_DEV_MODE and config.IOS_COMMERCE_ENABLED and (client_platform or "").lower() == "ios":
        return (config.CATALOG_ACCESSORY_CATEGORY_ID,) if config.CATALOG_ACCESSORY_CATEGORY_ID > 0 else ()
    return customer_category_scope(user_id)


async def require_catalog_products(
    session: AsyncSession, product_ids: Iterable[int], *, user_id: int, client_platform: str | None = None,
) -> None:
    scope = purchase_category_scope(user_id, client_platform=client_platform)
    if scope is None:
        return
    requested = set(product_ids)
    if not requested:
        return
    statement = select(Product.id).where(
        Product.id.in_(requested), Product.archived.is_(False), Product.is_visible_in_app.is_(True),
        Product.products_by_category.any(ProductByCategory.category_id.in_(scope)),
    )
    visible = set((await session.scalars(statement)).all())
    if requested != visible:
        raise HTTPException(status_code=404, detail="Product not found")
