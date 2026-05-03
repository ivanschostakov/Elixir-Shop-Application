from decimal import Decimal
from fastapi import HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.services.recommendations import record_cart_add
from src.database.crud import create_basket_item, get_basket_by_id, get_basket_by_user_id, get_order_draft_by_id
from src.database.crud.basket.basket_item import get_basket_item_by_basket_and_variant
from src.database.models import Basket, BasketItem, Variant
from src.database.schemas import BasketCreate, BasketItemRead, BasketProductSummaryRead, BasketRead, BasketVariantSummaryRead
from src.product_media import build_products_media_url


def _product_image_url(request: Request, product) -> str: return build_products_media_url(str(request.base_url), product.image_path)
def _variant_image_url(request: Request, variant) -> str: return build_products_media_url(str(request.base_url), variant.image_path)
def _basket_conflict(detail: str) -> HTTPException: return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


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
        basket = Basket(**BasketCreate(user_id=user_id).model_dump())
        db.add(basket)
        await db.commit()
        basket = await get_basket_by_user_id(db, user_id)
        if basket is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create basket")

    return basket


async def _get_variant_for_update(db: AsyncSession, variant_id: int) -> Variant | None:
    stmt = select(Variant).where(Variant.id == variant_id).with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_serialized_basket(request: Request, db: AsyncSession, user_id: int) -> BasketRead:
    basket = await _ensure_basket(db, user_id)
    return serialize_basket(request, basket)


async def _get_or_create_locked_basket(db: AsyncSession, user_id: int) -> Basket:
    stmt = select(Basket).where(Basket.user_id == user_id).with_for_update()
    basket = (await db.execute(stmt)).scalar_one_or_none()
    if basket is not None: return basket
    basket = Basket(user_id=user_id)
    db.add(basket)
    await db.flush()
    return basket


async def _lock_basket_items(db: AsyncSession, basket_id: int) -> None:
    stmt = select(BasketItem.id).where(BasketItem.basket_id == basket_id).with_for_update()
    await db.execute(stmt)


async def _get_locked_variants(db: AsyncSession, variant_ids: set[int]) -> dict[int, Variant]:
    if not variant_ids: return {}

    stmt = select(Variant).where(Variant.id.in_(variant_ids)).with_for_update()
    variants = list((await db.execute(stmt)).scalars().all())
    return {variant.id: variant for variant in variants}


async def add_variant_to_basket_for_user(db: AsyncSession, *, user_id: int, variant_id: int, quantity: int = 1, commit: bool = True) -> BasketItem:
    if quantity <= 0 or quantity > 100: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Quantity is invalid")

    basket = await _get_or_create_locked_basket(db, user_id)
    variant = await _get_variant_for_update(db, variant_id)
    if variant is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    existing_item = await get_basket_item_by_basket_and_variant(db, basket.id, variant.id, user_id=user_id)
    next_quantity = quantity if existing_item is None else existing_item.quantity + quantity
    if next_quantity > variant.stock: raise _basket_conflict("Requested quantity exceeds available stock")

    basket_item = await create_basket_item(db, basket_id=basket.id, user_id=user_id, product_id=variant.product_id, variant_id=variant.id, quantity=quantity, price=variant.price, commit=False)
    await record_cart_add(db, user_id=user_id, product_id=variant.product_id, quantity=quantity, commit=False)
    if commit: await db.commit()
    return basket_item


async def restore_order_draft_to_basket(request: Request, db: AsyncSession, *, user_id: int, draft_id: int) -> BasketRead:
    draft = await get_order_draft_by_id(db, draft_id, user_id=user_id)
    if draft is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")
    if not draft.items: raise _basket_conflict("Order draft is empty")

    basket = await _get_or_create_locked_basket(db, user_id)
    await _lock_basket_items(db, basket.id)

    variants_by_id = await _get_locked_variants(db, {item.variant_id for item in draft.items})
    restored_items: list[BasketItem] = []

    for draft_item in draft.items:
        variant = variants_by_id.get(draft_item.variant_id)
        if variant is None: raise _basket_conflict("Order draft contains unavailable items")
        if variant.stock <= 0 or draft_item.quantity > variant.stock: raise _basket_conflict("Order draft contains unavailable items")

        restored_items.append(
            BasketItem(
                basket_id=basket.id,
                user_id=user_id,
                product_id=variant.product_id,
                variant_id=variant.id,
                quantity=draft_item.quantity,
                price=variant.price,
            )
        )

    await db.execute(delete(BasketItem).where(BasketItem.basket_id == basket.id))
    db.add_all(restored_items)
    await db.flush()
    await db.commit()
    restored_basket = await get_basket_by_id(db, basket.id)
    if restored_basket is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load restored basket")
    return serialize_basket(request, restored_basket)
