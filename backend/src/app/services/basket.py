from decimal import Decimal

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import create_basket, get_basket_by_user_id
from src.database.models import Basket, Variant
from src.database.schemas import BasketCreate, BasketItemRead, BasketProductSummaryRead, BasketRead, BasketVariantSummaryRead
from src.product_media import build_products_media_url


def _product_image_url(request: Request, product) -> str:
    return build_products_media_url(str(request.base_url), product.image_path)


def _variant_image_url(request: Request, variant) -> str:
    return build_products_media_url(str(request.base_url), variant.image_path)


def serialize_basket(request: Request, basket: Basket) -> BasketRead:
    items = []
    total_quantity = 0
    total_amount = Decimal("0.00")
    has_unavailable_items = False

    sorted_items = sorted(basket.items, key=lambda item: (item.created_at, item.id))
    for item in sorted_items:
        unit_price = item.variant.price
        line_total = unit_price * item.quantity
        available_quantity = max(item.variant.stock, 0)
        is_available = available_quantity > 0 and item.quantity <= available_quantity
        has_unavailable_items = has_unavailable_items or not is_available
        total_quantity += item.quantity
        total_amount += line_total

        items.append(
            BasketItemRead(
                id=item.id,
                variant_id=item.variant_id,
                quantity=item.quantity,
                unit_price=unit_price,
                line_total=line_total,
                available_quantity=available_quantity,
                is_available=is_available,
                product=BasketProductSummaryRead(
                    id=item.product.id,
                    sku=item.product.sku,
                    name=item.product.name,
                    in_stock=item.product.in_stock,
                    image_url=_product_image_url(request, item.product),
                ),
                variant=BasketVariantSummaryRead(
                    id=item.variant.id,
                    sku=item.variant.sku,
                    name=item.variant.name,
                    stock=item.variant.stock,
                    price=item.variant.price,
                    image_url=_variant_image_url(request, item.variant),
                ),
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )

    return BasketRead(
        id=basket.id,
        user_id=basket.user_id,
        items=items,
        items_count=len(items),
        total_quantity=total_quantity,
        total_amount=total_amount,
        has_unavailable_items=has_unavailable_items,
        created_at=basket.created_at,
        updated_at=basket.updated_at,
    )


async def _ensure_basket(db: AsyncSession, user_id: int):
    basket = await get_basket_by_user_id(db, user_id)
    if basket is None:
        basket = await create_basket(db, BasketCreate(user_id=user_id))
    return basket


async def _get_variant_for_update(db: AsyncSession, variant_id: int) -> Variant | None:
    stmt = select(Variant).where(Variant.id == variant_id).with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_serialized_basket(request: Request, db: AsyncSession, user_id: int) -> BasketRead:
    basket = await _ensure_basket(db, user_id)
    return serialize_basket(request, basket)
