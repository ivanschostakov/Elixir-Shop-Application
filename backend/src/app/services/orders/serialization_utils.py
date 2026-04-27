from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import Product, Variant
from src.product_media import build_products_media_url


def build_order_item_image_url(request: Request, *, product: Product | None, variant: Variant | None) -> str:
    if variant is not None and variant.image_path is not None: return build_products_media_url(str(request.base_url), variant.image_path)
    if product is not None and product.image_path is not None: return build_products_media_url(str(request.base_url), product.image_path)
    return build_products_media_url(str(request.base_url), None)


async def get_products_by_id(session: AsyncSession, product_ids: set[int]) -> dict[int, Product]:
    if not product_ids: return {}
    stmt = select(Product).where(Product.id.in_(product_ids))
    return {product.id: product for product in (await session.execute(stmt)).scalars().all()}


async def get_variants_by_id(session: AsyncSession, variant_ids: set[int]) -> dict[int, Variant]:
    if not variant_ids: return {}
    stmt = select(Variant).options(selectinload(Variant.product)).where(Variant.id.in_(variant_ids))
    return {variant.id: variant for variant in (await session.execute(stmt)).scalars().all()}
