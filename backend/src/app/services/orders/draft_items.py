from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.database.crud import get_order_drafts_for_user
from src.database.models import Basket, BasketItem, OrderDraft, OrderDraftItem, Variant


def _checkout_conflict(detail: str | dict[str, Any]) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _build_items_signature(items: list[BasketItem] | list[OrderDraftItem]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted((item.variant_id, item.quantity) for item in items))


async def _find_duplicate_order_draft(session: AsyncSession, *, user_id: int, basket_items: list[BasketItem]) -> OrderDraft | None:
    basket_signature = _build_items_signature(basket_items)
    if not basket_signature: return None
    existing_drafts = await get_order_drafts_for_user(session, user_id, limit=None)

    for existing_draft in existing_drafts:
        if _build_items_signature(existing_draft.items) == basket_signature: return existing_draft

    return None


async def _get_locked_basket(session: AsyncSession, user_id: int) -> Basket | None:
    stmt = select(Basket).where(Basket.user_id == user_id).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def _get_locked_basket_items(session: AsyncSession, basket_id: int) -> list[BasketItem]:
    stmt = select(BasketItem).options(selectinload(BasketItem.product), selectinload(BasketItem.variant)).where(BasketItem.basket_id == basket_id).order_by(BasketItem.created_at.asc(), BasketItem.id.asc()).with_for_update()
    return list((await session.execute(stmt)).scalars().all())


async def _get_locked_variants(session: AsyncSession, variant_ids: list[int]) -> dict[int, Variant]:
    if not variant_ids: return {}

    stmt = select(Variant).where(Variant.id.in_(variant_ids)).with_for_update()
    variants = list((await session.execute(stmt)).scalars().all())
    return {variant.id: variant for variant in variants}


def _validate_checkout_items(items: list[BasketItem], variants_by_id: dict[int, Variant]) -> None:
    for item in items:
        variant = variants_by_id.get(item.variant_id)
        if variant is None: raise _checkout_conflict("Basket contains a variant that is no longer available")
        if variant.stock <= 0 or item.quantity > variant.stock: raise _checkout_conflict("Basket contains unavailable items")


def _build_draft_items_from_basket(*, user_id: int, draft_id: int, basket_items: list[BasketItem], variants_by_id: dict[int, Variant]) -> tuple[list[OrderDraftItem], Decimal, int]:
    basket_subtotal = Decimal("0.00")
    total_quantity = 0
    draft_items: list[OrderDraftItem] = []

    for basket_item in basket_items:
        variant = variants_by_id[basket_item.variant_id]
        unit_price = variant.price
        line_total = unit_price * basket_item.quantity
        basket_subtotal += line_total
        total_quantity += basket_item.quantity

        draft_items.append(
            OrderDraftItem(
                user_id=user_id,
                draft_id=draft_id,
                product_id=basket_item.product_id,
                variant_id=basket_item.variant_id,
                product_name=basket_item.product.name,
                product_sku=basket_item.product.sku,
                variant_name=variant.name,
                variant_sku=variant.sku,
                quantity=basket_item.quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    return draft_items, basket_subtotal, total_quantity


async def _sync_order_draft_items_from_basket(session: AsyncSession, *, draft: OrderDraft, user_id: int, update_data: dict[str, Decimal | int | str | None]) -> None:
    basket = await _get_locked_basket(session, user_id)
    basket_items = await _get_locked_basket_items(session, basket.id) if basket is not None else []

    delivery_total = update_data.get("delivery_total")
    if not isinstance(delivery_total, Decimal): delivery_total = draft.delivery_total
    if not basket_items:
        await session.execute(delete(OrderDraftItem).where(OrderDraftItem.draft_id == draft.id))
        if basket is not None: await session.execute(delete(BasketItem).where(BasketItem.basket_id == basket.id))

        update_data["items_count"] = 0
        update_data["total_quantity"] = 0
        update_data["basket_subtotal"] = Decimal("0.00")
        update_data["grand_total"] = delivery_total
        return

    variants_by_id = await _get_locked_variants(session, [item.variant_id for item in basket_items])
    _validate_checkout_items(basket_items, variants_by_id)
    draft_items, basket_subtotal, total_quantity = _build_draft_items_from_basket(
        user_id=user_id,
        draft_id=draft.id,
        basket_items=basket_items,
        variants_by_id=variants_by_id,
    )

    await session.execute(delete(OrderDraftItem).where(OrderDraftItem.draft_id == draft.id))
    session.add_all(draft_items)
    await session.execute(delete(BasketItem).where(BasketItem.basket_id == basket.id))

    update_data["items_count"] = len(draft_items)
    update_data["total_quantity"] = total_quantity
    update_data["basket_subtotal"] = basket_subtotal
    update_data["grand_total"] = basket_subtotal + delivery_total
