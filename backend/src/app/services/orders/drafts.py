from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.database.crud import create_delivery_address, create_delivery_recipient, create_order_draft, delete_order_draft, get_delivery_address_by_fields, get_delivery_address_by_id, get_delivery_addresses, get_delivery_recipient_by_fields, get_delivery_recipient_by_id, get_delivery_recipients, get_latest_named_order_draft_for_user, get_order_draft_by_id, get_order_drafts_for_user, update_order_draft
from src.database.limits import ORDER_DRAFT_COMMENT_MAX_LENGTH, ORDER_DRAFT_NAME_MAX_LENGTH
from src.database.models import BasketItem, OrderDraft, OrderDraftItem, User, Variant
from src.database.schemas import DeliveryAddressCreate, DeliveryAddressRead, DeliveryRecipientCreate, DeliveryRecipientRead, OrderDraftCheckoutOptionsRead, OrderDraftCreate, OrderDraftUpdate

from .draft_items import (
    _build_draft_items_from_basket,
    _checkout_conflict,
    _find_duplicate_order_draft,
    _get_locked_basket,
    _get_locked_basket_items,
    _get_locked_variants,
    _sync_order_draft_items_from_basket,
    _validate_checkout_items,
)
from .draft_normalization import (
    CREATE_ORDER_DRAFT_DELIVERY_FIELDS,
    REQUIRED_CREATE_ORDER_DRAFT_DELIVERY_FIELDS,
    _build_create_delivery_address_data,
    _build_new_delivery_address_data,
    _build_new_recipient_data,
    _normalize_order_draft_text,
)


async def _get_or_create_delivery_recipient(session: AsyncSession, *, data: DeliveryRecipientCreate):
    recipient = await get_delivery_recipient_by_fields(session, user_id=data.user_id, name=data.name, surname=data.surname, phone=data.phone, email=data.email)
    if recipient is not None: return recipient
    return await create_delivery_recipient(session, data, commit=False)


async def _get_or_create_delivery_address(session: AsyncSession, *, data: DeliveryAddressCreate):
    address = await get_delivery_address_by_fields(
        session,
        user_id=data.user_id,
        mode=data.mode,
        provider=data.provider,
        country_code=data.country_code,
        full_address=data.full_address,
        details=data.details,
        city=data.city,
        postal_code=data.postal_code,
        provider_reference=data.provider_reference,
    )
    if address is not None: return address
    return await create_delivery_address(session, data, commit=False)


async def create_order_draft_for_user(session: AsyncSession, *, user: User, payload) -> OrderDraft:
    basket = await _get_locked_basket(session, user.id)
    if basket is None: raise _checkout_conflict("Basket is empty")

    basket_items = await _get_locked_basket_items(session, basket.id)
    if not basket_items: raise _checkout_conflict("Basket is empty")

    variants_by_id = await _get_locked_variants(session, [item.variant_id for item in basket_items])
    _validate_checkout_items(basket_items, variants_by_id)

    duplicate_draft = await _find_duplicate_order_draft(session, user_id=user.id, basket_items=basket_items)
    if duplicate_draft is not None: raise _checkout_conflict({"message": "Черновик с такими товарами уже существует", "draft_id": duplicate_draft.id})

    has_any_delivery_payload = any(field in payload.model_fields_set for field in CREATE_ORDER_DRAFT_DELIVERY_FIELDS)
    if has_any_delivery_payload:
        missing_delivery_fields = [field_name for field_name in REQUIRED_CREATE_ORDER_DRAFT_DELIVERY_FIELDS if getattr(payload, field_name) is None]
        if missing_delivery_fields: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery data is incomplete")

    delivery_address = None
    if has_any_delivery_payload: delivery_address = await _get_or_create_delivery_address(session, data=_build_create_delivery_address_data(user.id, payload))

    draft_items, basket_subtotal, total_quantity = _build_draft_items_from_basket(user_id=user.id, draft_id=0, basket_items=basket_items, variants_by_id=variants_by_id)
    calculation = payload.delivery_calculation
    delivery_total = calculation.delivery_sum if calculation is not None else Decimal("0.00")
    currency = calculation.currency if calculation is not None else "RUB"
    delivery_period_min = calculation.period_min if calculation is not None else None
    delivery_period_max = calculation.period_max if calculation is not None else None
    order_draft = await create_order_draft(
        session,
        OrderDraftCreate(
            user_id=user.id,
            delivery_address_id=delivery_address.id if delivery_address is not None else None,
            recipient_id=None,
            status="draft",
            items_count=len(draft_items),
            total_quantity=total_quantity,
            basket_subtotal=basket_subtotal,
            delivery_total=delivery_total,
            grand_total=basket_subtotal + delivery_total,
            currency=currency,
            delivery_period_min=delivery_period_min,
            delivery_period_max=delivery_period_max,
            draft_name=_normalize_order_draft_text(payload.draft_name, max_length=ORDER_DRAFT_NAME_MAX_LENGTH),
            comment=None,
        ),
        commit=False,
    )

    for draft_item in draft_items:
        draft_item.draft_id = order_draft.id

    session.add_all(draft_items)
    await session.flush()
    await session.execute(delete(BasketItem).where(BasketItem.basket_id == basket.id))
    await session.commit()

    created_draft = await get_order_draft_by_id(session, order_draft.id, user_id=user.id)
    if created_draft is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order draft")

    return created_draft


def _normalize_ai_draft_items(items: list[dict[str, Any]]) -> dict[int, int]:
    normalized: dict[int, int] = {}
    for item in items:
        variant_id = int(item.get("variant_id") or 0)
        quantity = int(item.get("quantity") or 0)
        if variant_id <= 0 or quantity <= 0: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Draft item data is invalid")
        normalized[variant_id] = normalized.get(variant_id, 0) + quantity
    if not normalized: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Draft must contain at least one item")
    if any(quantity > 100 for quantity in normalized.values()): raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Draft item quantity is too large")
    return normalized


async def create_order_draft_from_variant_selection(session: AsyncSession, *, user: User, items: list[dict[str, Any]], draft_name: str | None = None, comment: str | None = None, commit: bool = True) -> OrderDraft:
    normalized_items = _normalize_ai_draft_items(items)
    stmt = select(Variant).options(selectinload(Variant.product)).where(Variant.id.in_(normalized_items.keys())).with_for_update()
    variants = list((await session.execute(stmt)).scalars().all())
    variants_by_id = {variant.id: variant for variant in variants}
    if len(variants_by_id) != len(normalized_items): raise _checkout_conflict("Some selected variants are no longer available")

    draft_items: list[OrderDraftItem] = []
    basket_subtotal = Decimal("0.00")
    total_quantity = 0

    for variant_id, quantity in normalized_items.items():
        variant = variants_by_id[variant_id]
        if variant.stock <= 0 or quantity > variant.stock: raise _checkout_conflict("Selected products are no longer available in the requested quantity")
        line_total = variant.price * quantity
        basket_subtotal += line_total
        total_quantity += quantity
        draft_items.append(
            OrderDraftItem(
                user_id=user.id,
                draft_id=0,
                product_id=variant.product_id,
                variant_id=variant.id,
                product_name=variant.product.name,
                product_sku=variant.product.sku,
                variant_name=variant.name,
                variant_sku=variant.sku,
                quantity=quantity,
                unit_price=variant.price,
                line_total=line_total,
            )
        )

    order_draft = await create_order_draft(
        session,
        OrderDraftCreate(
            user_id=user.id,
            delivery_address_id=None,
            recipient_id=None,
            status="draft",
            items_count=len(draft_items),
            total_quantity=total_quantity,
            basket_subtotal=basket_subtotal,
            delivery_total=Decimal("0.00"),
            grand_total=basket_subtotal,
            currency="RUB",
            delivery_period_min=None,
            delivery_period_max=None,
            draft_name=_normalize_order_draft_text(draft_name, max_length=ORDER_DRAFT_NAME_MAX_LENGTH),
            comment=_normalize_order_draft_text(comment, max_length=ORDER_DRAFT_COMMENT_MAX_LENGTH),
        ),
        commit=False,
    )

    for draft_item in draft_items: draft_item.draft_id = order_draft.id

    session.add_all(draft_items)
    await session.flush()

    if commit: await session.commit()

    created_draft = await get_order_draft_by_id(session, order_draft.id, user_id=user.id)
    if created_draft is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order draft")
    return created_draft


async def get_order_draft_for_user(session: AsyncSession, *, user_id: int, draft_id: int) -> OrderDraft | None:
    return await get_order_draft_by_id(session, draft_id, user_id=user_id)


async def get_latest_order_draft_for_checkout(session: AsyncSession, *, user_id: int) -> OrderDraft | None:
    return await get_latest_named_order_draft_for_user(session, user_id)


async def get_recent_order_drafts_for_user(session: AsyncSession, *, user_id: int, limit: int = 10, offset: int = 0, created_from: datetime | None = None, created_to: datetime | None = None) -> list[OrderDraft]:
    return await get_order_drafts_for_user(session, user_id, limit=limit, offset=offset, created_from=created_from, created_to=created_to, named_only=True)


async def delete_order_draft_for_user(session: AsyncSession, *, user_id: int, draft_id: int) -> bool:
    draft = await get_order_draft_by_id(session, draft_id, user_id=user_id)
    if draft is None: return False

    await delete_order_draft(session, draft)
    return True


async def get_order_draft_checkout_options_for_user(session: AsyncSession, *, user: User, draft_id: int, limit: int = 20) -> OrderDraftCheckoutOptionsRead | None:
    draft = await get_order_draft_by_id(session, draft_id, user_id=user.id)
    if draft is None: return None

    addresses = await get_delivery_addresses(session, user_id=user.id, limit=limit)
    recipients = await get_delivery_recipients(session, user.id, limit=limit)
    if draft.recipient is not None and not any(recipient.id == draft.recipient.id for recipient in recipients):
        recipients.insert(0, draft.recipient)

    return OrderDraftCheckoutOptionsRead(
        addresses=[DeliveryAddressRead.model_validate(address) for address in addresses],
        recipients=[DeliveryRecipientRead.model_validate(recipient) for recipient in recipients],
    )


async def update_order_draft_for_user(session: AsyncSession, *, user_id: int, draft_id: int, payload) -> OrderDraft | None:
    draft = await get_order_draft_by_id(session, draft_id, user_id=user_id)
    if draft is None: return None

    if "recipient_id" in payload.model_fields_set and payload.new_recipient is not None: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose an existing recipient or create a new one")
    if payload.delivery_address_id is not None and payload.new_delivery_address is not None: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose an existing address or create a new one")

    update_data: dict[str, Decimal | int | str | None] = {}
    if "draft_name" in payload.model_fields_set: update_data["draft_name"] = _normalize_order_draft_text(payload.draft_name, max_length=ORDER_DRAFT_NAME_MAX_LENGTH)
    if "comment" in payload.model_fields_set: update_data["comment"] = _normalize_order_draft_text(payload.comment, max_length=ORDER_DRAFT_COMMENT_MAX_LENGTH)
    if "recipient_id" in payload.model_fields_set:
        if payload.recipient_id is None: update_data["recipient_id"] = None
        else:
            recipient = await get_delivery_recipient_by_id(session, payload.recipient_id, user_id=user_id)
            if recipient is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery recipient not found")
            update_data["recipient_id"] = recipient.id

    if payload.new_recipient is not None:
        created_recipient = await _get_or_create_delivery_recipient(session, data=_build_new_recipient_data(user_id, payload.new_recipient))
        update_data["recipient_id"] = created_recipient.id

    if payload.delivery_address_id is not None:
        delivery_address = await get_delivery_address_by_id(session, payload.delivery_address_id)
        if delivery_address is None or delivery_address.user_id != user_id: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery address not found")
        update_data["delivery_address_id"] = delivery_address.id

    if payload.new_delivery_address is not None:
        created_address = await _get_or_create_delivery_address(session, data=_build_new_delivery_address_data(draft, payload.new_delivery_address))
        update_data["delivery_address_id"] = created_address.id
        if payload.new_delivery_address.delivery_calculation is not None:
            delivery_total = payload.new_delivery_address.delivery_calculation.delivery_sum
            update_data["delivery_total"] = delivery_total
            update_data["currency"] = payload.new_delivery_address.delivery_calculation.currency
            update_data["delivery_period_min"] = payload.new_delivery_address.delivery_calculation.period_min
            update_data["delivery_period_max"] = payload.new_delivery_address.delivery_calculation.period_max
            update_data["grand_total"] = draft.basket_subtotal + delivery_total

    if payload.sync_basket_items: await _sync_order_draft_items_from_basket(session, draft=draft, user_id=user_id, update_data=update_data)

    update_payload = OrderDraftUpdate(**update_data)
    updated_draft = await update_order_draft(session, draft, update_payload)
    return await get_order_draft_by_id(session, updated_draft.id, user_id=user_id)
