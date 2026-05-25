import secrets

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from config import ufa_now
from src.app.modules.guest.schemas import GuestBasketItemPayload, GuestBasketQuoteRead, GuestDeliveryAddressPayload, GuestOrderPayload
from src.app.services.basket import _product_image_url, _variant_image_url
from src.app.services.orders.creation import (
    _build_checkout_snapshot,
    _build_selected_delivery_payload,
    _delivery_string,
    _generate_order_code,
)
from src.app.services.orders.crm import ensure_order_has_amocrm_lead
from src.app.services.orders.fulfillment_payloads import normalize_address_for_cf
from src.app.services.recommendations import record_purchase
from src.app.services.security import hash_password
from src.database.crud import create_delivery_address, create_delivery_recipient, create_order, get_order_by_id
from src.database.crud import get_delivery_recipient_by_fields
from src.database.crud.auth.user import create_user, get_user_by_email, get_user_by_username
from src.database.models import OrderItem, Product, User, Variant
from src.database.schemas import (
    BasketItemRead,
    BasketProductSummaryRead,
    BasketVariantSummaryRead,
    DeliveryAddressCreate,
    DeliveryRecipientCreate,
    OrderCreate,
    UserCreate,
)
from src.integrations.amocrm import get_amocrm_client
from src.integrations.moysklad.order_sync import sync_order_to_moysklad_safe

amocrm_client = get_amocrm_client()


def _normalize_guest_items(items: list[GuestBasketItemPayload]) -> dict[int, int]:
    normalized: dict[int, int] = {}
    for item in items: normalized[item.variant_id] = normalized.get(item.variant_id, 0) + item.quantity
    if any(quantity > 100 for quantity in normalized.values()): raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Quantity is invalid")
    return normalized


async def _load_guest_variants(session: AsyncSession, items_by_variant_id: dict[int, int], *, lock: bool = False) -> dict[int, Variant]:
    if not items_by_variant_id: return {}
    stmt = select(Variant).options(selectinload(Variant.product)).where(Variant.id.in_(items_by_variant_id.keys()))
    if lock: stmt = stmt.with_for_update()
    variants = list((await session.execute(stmt)).scalars().all())
    return {variant.id: variant for variant in variants}


def _validate_guest_variants(items_by_variant_id: dict[int, int], variants_by_id: dict[int, Variant]) -> None:
    if len(variants_by_id) != len(items_by_variant_id): raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    for variant_id, quantity in items_by_variant_id.items():
        variant = variants_by_id[variant_id]
        if variant.archived or variant.stock <= 0: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Basket contains unavailable items")
        if quantity > variant.stock: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requested quantity exceeds available stock")


def _guest_basket_item_read(request: Request, *, variant: Variant, quantity: int, now: datetime) -> BasketItemRead:
    product = variant.product
    if product is None: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Basket contains unavailable items")
    line_total = variant.price * quantity
    return BasketItemRead(id=variant.id, variant_id=variant.id, quantity=quantity, unit_price=variant.price, line_total=line_total, available_quantity=max(variant.stock, 0), is_available=variant.stock > 0 and quantity <= variant.stock, product=BasketProductSummaryRead(
        id=product.id,
        sku=product.sku,
        name=product.name,
        in_stock=product.in_stock,
        image_url=_product_image_url(request, product),
    ), variant=BasketVariantSummaryRead(
        id=variant.id,
        sku=variant.sku,
        name=variant.name,
        stock=variant.stock,
        price=variant.price,
        image_url=_variant_image_url(request, variant),
    ), created_at=now, updated_at=now)


async def quote_guest_basket(session: AsyncSession, request: Request, payload: list[GuestBasketItemPayload]) -> GuestBasketQuoteRead:
    now = ufa_now()
    items_by_variant_id = _normalize_guest_items(payload)
    variants_by_id = await _load_guest_variants(session, items_by_variant_id)
    _validate_guest_variants(items_by_variant_id, variants_by_id)

    items: list[BasketItemRead] = []
    total_quantity = 0
    total_amount = Decimal("0.00")
    for variant_id in sorted(items_by_variant_id.keys()):
        quantity = items_by_variant_id[variant_id]
        variant = variants_by_id[variant_id]
        item = _guest_basket_item_read(request, variant=variant, quantity=quantity, now=now)
        items.append(item)
        total_quantity += quantity
        total_amount += item.line_total

    return GuestBasketQuoteRead(
        id=-1,
        user_id=0,
        items=items,
        delivery_address_id=None,
        recipient_id=None,
        delivery_address=None,
        recipient=None,
        items_count=len(items),
        total_quantity=total_quantity,
        total_amount=total_amount,
        delivery_total=Decimal("0.00"),
        grand_total=total_amount,
        currency="RUB",
        delivery_period_min=None,
        delivery_period_max=None,
        has_unavailable_items=False,
        created_at=now,
        updated_at=now,
    )


async def generate_guest_username(session: AsyncSession) -> str:
    for _ in range(30):
        username = f"guest{secrets.token_hex(5)}"
        if await get_user_by_username(session, username) is None: return username

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate username")


def generate_guest_password() -> str: return secrets.token_urlsafe(12)
def _delivery_address_create(user_id: int, payload: GuestDeliveryAddressPayload) -> DeliveryAddressCreate:
    return DeliveryAddressCreate(
        user_id=user_id,
        mode=payload.mode,
        provider=payload.provider,
        country_code=payload.country_code,
        name=payload.name,
        full_address=payload.full_address,
        details=payload.details,
        city=payload.city,
        postal_code=payload.postal_code,
        latitude=payload.latitude,
        longitude=payload.longitude,
        provider_reference=payload.provider_reference,
    )


async def create_guest_order(session: AsyncSession, request: Request, payload: GuestOrderPayload) -> tuple[User, str, Any]:
    normalized_email = str(payload.recipient.email).strip().lower()
    existing_user = await get_user_by_email(session, normalized_email)
    if existing_user is not None and existing_user.is_active: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "email_exists", "message": "User with this email already exists"})

    items_by_variant_id = _normalize_guest_items(payload.items)
    variants_by_id = await _load_guest_variants(session, items_by_variant_id, lock=True)
    _validate_guest_variants(items_by_variant_id, variants_by_id)

    username = await generate_guest_username(session)
    password = generate_guest_password()
    user = await create_user(session, UserCreate(
        username=username,
        email=normalized_email,
        name=payload.recipient.name,
        surname=payload.recipient.surname,
        phone_number=payload.recipient.phone,
        password_hash=hash_password(password),
        is_verified=True,
    ), commit=False)

    delivery_address = await create_delivery_address(session, _delivery_address_create(user.id, payload.delivery_address), commit=False)
    recipient_data = DeliveryRecipientCreate(user_id=user.id, name=payload.recipient.name, surname=payload.recipient.surname, phone=payload.recipient.phone, email=normalized_email)
    recipient = await get_delivery_recipient_by_fields(session, user_id=recipient_data.user_id, name=recipient_data.name, surname=recipient_data.surname, phone=recipient_data.phone, email=recipient_data.email)
    if recipient is None: recipient = await create_delivery_recipient(session, recipient_data, commit=False)

    basket_subtotal = Decimal("0.00")
    total_quantity = 0
    checkout_items = []
    order_items: list[OrderItem] = []

    for variant_id in sorted(items_by_variant_id.keys()):
        quantity = items_by_variant_id[variant_id]
        variant = variants_by_id[variant_id]
        product: Product | None = variant.product
        if product is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Basket contains unavailable items")
        line_total = variant.price * quantity
        basket_subtotal += line_total
        total_quantity += quantity
        checkout_items.append(
            SimpleNamespace(
                product_id=product.id,
                variant_id=variant.id,
                product_name=product.name,
                product_sku=product.sku,
                variant_name=variant.name,
                quantity=quantity,
                unit_price=variant.price,
                line_total=line_total,
            )
        )

    checkout_source = SimpleNamespace(
        delivery_address=delivery_address,
        delivery_address_id=delivery_address.id,
        recipient=recipient,
        recipient_id=recipient.id,
        items=checkout_items,
        basket_subtotal=basket_subtotal,
        delivery_total=payload.delivery_address.delivery_calculation.delivery_sum,
        grand_total=basket_subtotal + payload.delivery_address.delivery_calculation.delivery_sum,
        currency=payload.delivery_address.delivery_calculation.currency,
        delivery_period_min=payload.delivery_address.delivery_calculation.period_min,
        delivery_period_max=payload.delivery_address.delivery_calculation.period_max,
        comment=None,
    )
    selected_delivery_service, selected_delivery_payload = await _build_selected_delivery_payload(checkout_source)
    checkout_snapshot = _build_checkout_snapshot(
        checkout_source,
        payment_method=payload.payment_method,
        selected_delivery_service=selected_delivery_service,
        selected_delivery_payload=selected_delivery_payload,
        resolved_benefits=None,
    )
    delivery_string = _delivery_string(selected_delivery_service, normalize_address_for_cf(selected_delivery_payload.get("address")))
    order_code = await _generate_order_code(session)
    order = await create_order(
        session,
        OrderCreate(
            draft_id=None,
            user_id=user.id,
            delivery_address_id=delivery_address.id,
            recipient_id=recipient.id,
            order_code=order_code,
            status=amocrm_client.STATUS_WORDS.get(amocrm_client.STATUS_IDS["main"], "Создан"),
            items_count=len(checkout_items),
            total_quantity=total_quantity,
            basket_subtotal=basket_subtotal,
            delivery_total=checkout_source.delivery_total,
            grand_total=checkout_source.grand_total,
            currency=checkout_source.currency,
            delivery_period_min=checkout_source.delivery_period_min,
            delivery_period_max=checkout_source.delivery_period_max,
            comment=None,
            delivery_string=delivery_string,
            selected_delivery_service=selected_delivery_service,
            selected_delivery_payload=selected_delivery_payload,
            checkout_snapshot=checkout_snapshot,
            payment_method=payload.payment_method,
            payment_provider=None,
            payment_status="draft",
            payment_invoice_id=None,
            payment_paid_at=None,
            payment_error=None,
            amocrm_lead_id=None,
            delivery_created_at=None,
            delivery_provider_ref=None,
            yandex_request_id=None,
            is_active=True,
            is_paid=False,
            is_canceled=False,
            is_shipped=False,
        ),
        commit=False,
    )

    for variant_id in sorted(items_by_variant_id.keys()):
        quantity = items_by_variant_id[variant_id]
        variant = variants_by_id[variant_id]
        product = variant.product
        if product is None: continue
        line_total = variant.price * quantity
        order_items.append(OrderItem(
            user_id=user.id,
            order_id=order.id,
            product_id=product.id,
            variant_id=variant.id,
            product_name=product.name,
            product_sku=product.sku,
            variant_name=variant.name,
            variant_sku=variant.sku,
            quantity=quantity,
            unit_price=variant.price,
            line_total=line_total,
        ))
    session.add_all(order_items)
    await session.flush()
    for order_item in order_items: await record_purchase(session, user_id=user.id, product_id=order_item.product_id, quantity=order_item.quantity, commit=False)
    await ensure_order_has_amocrm_lead(session, order, user=user)
    await session.commit()
    await session.refresh(user)
    created_order = await get_order_by_id(session, order.id, user_id=user.id)
    if created_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order")
    await sync_order_to_moysklad_safe(session, order=created_order, user=user)
    return user, password, created_order
