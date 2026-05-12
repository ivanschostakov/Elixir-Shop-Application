from decimal import Decimal
from types import SimpleNamespace
from fastapi import HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.services.recommendations import record_cart_add
from src.database.crud import (
    create_basket_item,
    create_delivery_address,
    create_delivery_recipient,
    get_basket_by_id,
    get_basket_by_user_id,
    get_delivery_address_by_fields,
    get_delivery_address_by_id,
    get_delivery_addresses,
    get_delivery_recipient_by_fields,
    get_delivery_recipient_by_id,
    get_delivery_recipients,
    get_order_draft_by_id,
    update_basket,
)
from src.database.crud.basket.basket_item import get_basket_item_by_basket_and_variant
from src.database.models import Basket, BasketItem, User, Variant
from src.database.schemas import (
    BasketCreate,
    BasketItemRead,
    BasketProductSummaryRead,
    BasketRead,
    BasketUpdate,
    BasketVariantSummaryRead,
    DeliveryAddressCreate,
    DeliveryAddressRead,
    DeliveryRecipientCreate,
    DeliveryRecipientRead,
    OrderDraftCheckoutOptionsRead,
)
from src.product_media import build_products_media_url

from .orders.draft_normalization import _build_new_delivery_address_data, _build_new_recipient_data
from .orders.common import _normalize_phone


def _product_image_url(request: Request, product) -> str: return build_products_media_url(str(request.base_url), product.image_path)
def _variant_image_url(request: Request, variant) -> str: return build_products_media_url(str(request.base_url), variant.image_path)
def _basket_conflict(detail: str) -> HTTPException: return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _is_self_like_recipient(*, recipient, user: User) -> bool:
    recipient_name = str(recipient.name or "").strip().lower()
    recipient_surname = str(recipient.surname or "").strip().lower()
    recipient_email = str(recipient.email or "").strip().lower()
    recipient_phone = _normalize_phone(recipient.phone) or ""
    user_name = str(user.name or "").strip().lower()
    user_surname = str(user.surname or "").strip().lower()
    user_email = str(user.email or "").strip().lower()
    user_phone = _normalize_phone(user.phone_number) or ""
    return (
        recipient_name == user_name
        and recipient_surname == user_surname
        and recipient_email == user_email
        and recipient_phone == user_phone
    )


def _filter_self_like_recipients(*, recipients: list, user: User) -> list:
    return [recipient for recipient in recipients if not _is_self_like_recipient(recipient=recipient, user=user)]


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
        delivery_address_id=basket.delivery_address_id,
        recipient_id=basket.recipient_id,
        delivery_address=DeliveryAddressRead.model_validate(basket.delivery_address) if basket.delivery_address is not None else None,
        recipient=DeliveryRecipientRead.model_validate(basket.recipient) if basket.recipient is not None else None,
        items_count=len(items),
        total_quantity=total_quantity,
        total_amount=total_amount,
        delivery_total=basket.delivery_total,
        grand_total=total_amount + basket.delivery_total,
        currency=basket.currency,
        delivery_period_min=basket.delivery_period_min,
        delivery_period_max=basket.delivery_period_max,
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


async def get_basket_checkout_options_for_user(db: AsyncSession, *, user: User, limit: int = 20) -> OrderDraftCheckoutOptionsRead:
    basket = await _ensure_basket(db, user.id)
    addresses = await get_delivery_addresses(db, user_id=user.id, limit=limit)
    recipients = _filter_self_like_recipients(
        recipients=await get_delivery_recipients(db, user.id, limit=limit),
        user=user,
    )

    if basket.delivery_address is not None and not any(address.id == basket.delivery_address.id for address in addresses):
        addresses.insert(0, basket.delivery_address)
    if (
        basket.recipient is not None
        and not _is_self_like_recipient(recipient=basket.recipient, user=user)
        and not any(recipient.id == basket.recipient.id for recipient in recipients)
    ):
        recipients.insert(0, basket.recipient)

    return OrderDraftCheckoutOptionsRead(
        addresses=[DeliveryAddressRead.model_validate(address) for address in addresses],
        recipients=[DeliveryRecipientRead.model_validate(recipient) for recipient in recipients],
    )


async def _get_or_create_delivery_recipient(db: AsyncSession, *, data: DeliveryRecipientCreate):
    recipient = await get_delivery_recipient_by_fields(db, user_id=data.user_id, name=data.name, surname=data.surname, phone=data.phone, email=data.email)
    if recipient is not None: return recipient
    return await create_delivery_recipient(db, data, commit=False)


async def _get_or_create_delivery_address(db: AsyncSession, *, data: DeliveryAddressCreate):
    address = await get_delivery_address_by_fields(
        db,
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
    return await create_delivery_address(db, data, commit=False)


async def update_basket_checkout_for_user(request: Request, db: AsyncSession, *, user: User, payload) -> BasketRead:
    basket = await _ensure_basket(db, user.id)

    if "recipient_id" in payload.model_fields_set and payload.new_recipient is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose an existing recipient or create a new one")
    if payload.delivery_address_id is not None and payload.new_delivery_address is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose an existing address or create a new one")

    update_data: dict[str, Decimal | int | str | None] = {}

    if "recipient_id" in payload.model_fields_set:
        if payload.recipient_id is None:
            update_data["recipient_id"] = None
        else:
            recipient = await get_delivery_recipient_by_id(db, payload.recipient_id, user_id=user.id)
            if recipient is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery recipient not found")
            update_data["recipient_id"] = recipient.id

    if payload.new_recipient is not None:
        recipient = await _get_or_create_delivery_recipient(db, data=_build_new_recipient_data(user.id, payload.new_recipient))
        update_data["recipient_id"] = recipient.id

    if payload.delivery_address_id is not None:
        address = await get_delivery_address_by_id(db, payload.delivery_address_id)
        if address is None or address.user_id != user.id: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery address not found")
        update_data["delivery_address_id"] = address.id

    if payload.new_delivery_address is not None:
        address = await _get_or_create_delivery_address(
            db,
            data=_build_new_delivery_address_data(
                SimpleNamespace(user_id=user.id, delivery_address=basket.delivery_address),
                payload.new_delivery_address,
            ),
        )
        update_data["delivery_address_id"] = address.id
        if payload.new_delivery_address.delivery_calculation is not None:
            update_data["delivery_total"] = payload.new_delivery_address.delivery_calculation.delivery_sum
            update_data["currency"] = payload.new_delivery_address.delivery_calculation.currency
            update_data["delivery_period_min"] = payload.new_delivery_address.delivery_calculation.period_min
            update_data["delivery_period_max"] = payload.new_delivery_address.delivery_calculation.period_max

    await update_basket(db, basket, BasketUpdate(**update_data))
    updated_basket = await get_basket_by_id(db, basket.id)
    if updated_basket is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load basket")
    return serialize_basket(request, updated_basket)


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
    if variant is None or variant.archived: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

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
        if variant.archived or variant.stock <= 0 or draft_item.quantity > variant.stock: raise _basket_conflict("Order draft contains unavailable items")

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
