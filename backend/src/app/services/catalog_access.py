"""One published product catalog for every customer, guest and platform."""
from collections.abc import Iterable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Product

CatalogScope = tuple[int, ...] | None


def customer_category_scope(user_id: int | None) -> CatalogScope:
    return None


def purchase_category_scope(user_id: int | None, *, client_platform: str | None = None) -> CatalogScope:
    return None


async def require_catalog_products(
    session: AsyncSession, product_ids: Iterable[int], *, user_id: int, client_platform: str | None = None,
) -> None:
    requested = set(product_ids)
    if not requested:
        return
    statement = select(Product.id).where(
        Product.id.in_(requested), Product.archived.is_(False), Product.is_visible_in_app.is_(True),
    )
    visible = set((await session.scalars(statement)).all())
    if requested != visible:
        raise HTTPException(status_code=404, detail="Product not found")
