from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import secrets
from typing import Any
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.app.services.recommendations import record_purchase
from src.database.crud import create_delivery_recipient, create_order, create_order_draft, delete_order_draft, get_delivery_recipient_by_fields, get_order_by_code, get_order_by_draft_id, get_order_by_id, get_order_draft_by_id, get_orders_for_user as get_orders_for_user_crud
from src.database.models import Order, OrderDraft, OrderDraftItem, OrderItem, User, Variant
from src.database.models.orders.history import OrderHistoryBucket, OrderStatusCode, get_order_history_bucket
from src.database.schemas import DeliveryRecipientCreate, OrderCreate, OrderDraftCreate
from src.integrations.amocrm import amocrm_client
from src.integrations.delivery.cdek import get_cdek_client

from .common import _delivery_string, _normalize_phone
from .crm import ensure_order_has_amocrm_lead
from .fulfillment import normalize_address_for_cf

ORDER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


async def _generate_order_code(session: AsyncSession) -> str:
    for _ in range(20):
        suffix = "".join(secrets.choice(ORDER_CODE_ALPHABET) for _ in range(8))
        order_code = f"EP-{suffix}"
        if await get_order_by_code(session, order_code) is None:
            return order_code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate order code")


async def _get_or_create_self_recipient(session: AsyncSession, *, user: User):
    email = (user.email or "").strip().lower()
    phone = _normalize_phone(user.phone_number) or ""
    recipient = await get_delivery_recipient_by_fields(session, user_id=user.id, name=user.name, surname=user.surname, phone=phone, email=email)
    if recipient is not None: return recipient

    return await create_delivery_recipient(session, DeliveryRecipientCreate(user_id=user.id, name=user.name, surname=user.surname, phone=phone, email=email), commit=False)

async def _clear_order_draft_references(session: AsyncSession, *, draft_id: int) -> None:
    linked_orders = list((await session.execute(select(Order).where(Order.draft_id == draft_id))).scalars().all())
    if not linked_orders: return

    for linked_order in linked_orders:
        linked_order.draft = None
        linked_order.draft_id = None

    await session.flush()

def _build_selected_delivery_payload(draft: OrderDraft) -> tuple[str, dict[str, Any]]:
    if draft.delivery_address is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery address is required")

    delivery_address = draft.delivery_address
    address_payload = {"code": delivery_address.provider_reference, "name": delivery_address.name, "address": delivery_address.full_address, "formatted": delivery_address.full_address, "full_address": delivery_address.full_address, "details": delivery_address.details, "city": delivery_address.city, "postal_code": delivery_address.postal_code, "country_code": delivery_address.country_code, "latitude": delivery_address.latitude, "longitude": delivery_address.longitude, "provider_reference": delivery_address.provider_reference, }
    delivery_total = float(draft.delivery_total)

    if delivery_address.provider == "CDEK":
        delivery_mode = "office" if delivery_address.mode == "pickup" else "door"
        payload = {"deliveryMode": delivery_mode, "tariff": {"tariff_code": get_cdek_client().tariff_codes[delivery_mode], "tariff_name": delivery_mode, "delivery_sum": delivery_total, }, "address": address_payload, "delivery_sum": delivery_total, }
        return "CDEK", payload

    if delivery_address.provider == "YANDEX":
        if delivery_address.mode != "pickup":raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Yandex door delivery is not supported in this flow")
        payload = {"deliveryMode": "self_pickup", "tariff": {"tariff_name": "self_pickup", }, "address": address_payload, "delivery_sum": delivery_total, }
        return "YANDEX", payload

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported delivery provider")


def _build_checkout_snapshot(draft: OrderDraft, *, payment_method: str, selected_delivery_service: str, selected_delivery_payload: dict[str, Any]) -> dict[str, Any]:
    if draft.recipient is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Recipient is required")

    items = [{"id": item.product_id, "featureId": item.variant_id, "name": item.product_name, "product_name": item.product_name, "feature_name": item.variant_name, "code": item.product_sku, "qty": item.quantity, "price": float(item.unit_price), "subtotal": float(item.line_total)} for item in draft.items]

    return {"source": "shop_application", "payment_method": payment_method, "contact_info": {"name": draft.recipient.name, "surname": draft.recipient.surname, "phone": draft.recipient.phone, "email": draft.recipient.email, }, "checkout_data": {"items": items, "total": float(draft.basket_subtotal), }, "selected_delivery": deepcopy(selected_delivery_payload), "selected_delivery_service": selected_delivery_service, "commentary": draft.comment or "Не указан", "order_date": datetime.now(timezone.utc).isoformat()}

async def create_order_from_draft_for_user(session: AsyncSession, *, user: User, draft_id: int, payment_method: str) -> Order:
    draft = await get_order_draft_by_id(session, draft_id, user_id=user.id)
    if draft is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")

    existing_order = await get_order_by_draft_id(session, draft.id, user_id=user.id)
    if existing_order is not None:
        await _clear_order_draft_references(session, draft_id=draft.id)
        await delete_order_draft(session, draft, commit=False)
        await session.commit()

        refreshed_order = await get_order_by_id(session, existing_order.id, user_id=user.id)
        if refreshed_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load existing order")
        return refreshed_order

    if draft.recipient is None:
        recipient = await _get_or_create_self_recipient(session, user=user)
        draft.recipient_id = recipient.id
        draft.recipient = recipient
        await session.flush()

    if draft.delivery_address is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery address is required")
    if not draft.items: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order draft is empty")

    selected_delivery_service, selected_delivery_payload = _build_selected_delivery_payload(draft)
    checkout_snapshot = _build_checkout_snapshot(draft, payment_method=payment_method, selected_delivery_service=selected_delivery_service, selected_delivery_payload=selected_delivery_payload)
    delivery_string = _delivery_string(selected_delivery_service, normalize_address_for_cf(selected_delivery_payload.get("address")))

    order_code = await _generate_order_code(session)
    order = await create_order(session, OrderCreate(draft_id=None, user_id=user.id, delivery_address_id=draft.delivery_address_id, recipient_id=draft.recipient_id, order_code=order_code, status=amocrm_client.STATUS_WORDS.get(amocrm_client.STATUS_IDS["main"], "Создан"), items_count=draft.items_count, total_quantity=draft.total_quantity, basket_subtotal=draft.basket_subtotal, delivery_total=draft.delivery_total, grand_total=draft.grand_total, currency=draft.currency, delivery_period_min=draft.delivery_period_min, delivery_period_max=draft.delivery_period_max, comment=draft.comment, delivery_string=delivery_string, selected_delivery_service=selected_delivery_service, selected_delivery_payload=selected_delivery_payload, checkout_snapshot=checkout_snapshot, payment_method=payment_method, payment_provider=None, payment_status="draft", payment_invoice_id=None, payment_paid_at=None, payment_error=None, amocrm_lead_id=None, delivery_created_at=None, delivery_provider_ref=None, yandex_request_id=None, is_active=True, is_paid=False, is_canceled=False, is_shipped=False), commit=False)

    order_items = [OrderItem(user_id=user.id, order_id=order.id, product_id=item.product_id, variant_id=item.variant_id, product_name=item.product_name, product_sku=item.product_sku, variant_name=item.variant_name, variant_sku=item.variant_sku, quantity=item.quantity, unit_price=item.unit_price, line_total=item.line_total) for item in draft.items]
    session.add_all(order_items)
    await session.flush()
    for item in draft.items: await record_purchase(session, user_id=user.id, product_id=item.product_id, quantity=item.quantity, commit=False)
    await ensure_order_has_amocrm_lead(session, order, user=user)
    await _clear_order_draft_references(session, draft_id=draft.id)
    await delete_order_draft(session, draft, commit=False)
    await session.commit()

    created_order = await get_order_by_id(session, order.id, user_id=user.id)
    if created_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order")

    return created_order


async def get_order_for_user(session: AsyncSession, *, user_id: int, order_id: int) -> Order | None: return await get_order_by_id(session, order_id, user_id=user_id)
async def get_orders_history_for_user(session: AsyncSession, *, user_id: int, history_bucket: OrderHistoryBucket | None = None, status_code: OrderStatusCode | None = None, created_from: datetime | None = None, created_to: datetime | None = None, limit: int = 20, offset: int = 0) -> list[Order]: return await get_orders_for_user_crud(session, user_id, history_bucket=history_bucket, status_code=status_code, created_from=created_from, created_to=created_to, limit=limit, offset=offset)


async def _get_locked_variants_for_repeat(session: AsyncSession, variant_ids: list[int]) -> dict[int, Variant]:
    if not variant_ids:
        return {}

    stmt = (
        select(Variant)
        .options(selectinload(Variant.product))
        .where(Variant.id.in_(variant_ids))
        .with_for_update()
    )
    variants = list((await session.execute(stmt)).scalars().all())
    return {variant.id: variant for variant in variants}


async def repeat_order_as_draft_for_user(session: AsyncSession, *, user_id: int, order_id: int) -> OrderDraft | None:
    order = await get_order_by_id(session, order_id, user_id=user_id)
    if order is None:
        return None
    if get_order_history_bucket(order) != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Повторить можно только завершенный заказ")
    if not order.items:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order is empty")

    variants_by_id = await _get_locked_variants_for_repeat(session, [item.variant_id for item in order.items])
    draft_items: list[OrderDraftItem] = []
    basket_subtotal = Decimal("0.00")
    total_quantity = 0

    for order_item in order.items:
        variant = variants_by_id.get(order_item.variant_id)
        if variant is None or variant.product is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order contains unavailable items")
        if variant.stock <= 0 or order_item.quantity > variant.stock:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order contains unavailable items")

        line_total = variant.price * order_item.quantity
        basket_subtotal += line_total
        total_quantity += order_item.quantity
        draft_items.append(
            OrderDraftItem(
                user_id=user_id,
                draft_id=0,
                product_id=variant.product_id,
                variant_id=variant.id,
                product_name=variant.product.name,
                product_sku=variant.product.sku,
                variant_name=variant.name,
                variant_sku=variant.sku,
                quantity=order_item.quantity,
                unit_price=variant.price,
                line_total=line_total,
            )
        )

    draft = await create_order_draft(
        session,
        OrderDraftCreate(
            user_id=user_id,
            delivery_address_id=order.delivery_address_id,
            recipient_id=order.recipient_id,
            status="draft",
            items_count=len(draft_items),
            total_quantity=total_quantity,
            basket_subtotal=basket_subtotal,
            delivery_total=order.delivery_total,
            grand_total=basket_subtotal + order.delivery_total,
            currency=order.currency,
            delivery_period_min=order.delivery_period_min,
            delivery_period_max=order.delivery_period_max,
            draft_name=f"Повтор заказа №{order.order_number}",
            comment=order.comment,
        ),
        commit=False,
    )

    for draft_item in draft_items:
        draft_item.draft_id = draft.id

    session.add_all(draft_items)
    await session.flush()
    await session.commit()

    created_draft = await get_order_draft_by_id(session, draft.id, user_id=user_id)
    if created_draft is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load repeated order draft")

    return created_draft
