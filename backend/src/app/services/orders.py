from __future__ import annotations

import logging
import re
import socket

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from config import APP_PAYMENT_RETURN_BASE_URL
from src.app.services.order_fulfillment import create_delivery_for_order, normalize_address_for_cf
from src.app.services.order_payment_qr_storage import (
    build_order_payment_qr_url,
    find_order_payment_qr_path,
    save_order_payment_qr,
)
from src.app.services.push_notifications import send_order_status_change_notification_if_needed
from src.app.services.recommendations import record_purchase
from src.database.crud import (
    create_delivery_recipient,
    delete_order_draft,
    create_order,
    get_delivery_recipient_by_fields,
    get_order_by_id,
    get_order_by_draft_id,
    get_order_draft_by_id,
    get_orders_for_user as get_orders_for_user_crud,
    update_order,
)
from src.database.models import Order, OrderDraft, OrderItem, Product, User, Variant
from src.database.models.orders.history import (
    OrderHistoryBucket,
    OrderStatusCode,
    get_order_history_bucket,
    get_order_status_code,
)
from src.database.schemas import DeliveryRecipientCreate, OrderCreate, OrderItemRead, OrderRead, OrderUpdate
from src.integrations.amocrm import amocrm_client
from src.integrations.delivery.cdek import get_cdek_client
from src.integrations.intellectmoney import IntellectMoneyError, intellectmoney
from src.product_media import build_products_media_url

log = logging.getLogger(__name__)

Q2 = Decimal("0.01")
PAYMENT_STATUS_BY_CODE = {
    3: "created",
    4: "canceled",
    5: "paid",
    6: "hold",
    7: "partial",
    8: "refunded",
}
PENDING_PAYMENT_STEPS = {"", "Created", "InProcess", "SendTo3DS"}
FINAL_PAYMENT_STATUSES = {"paid", "canceled", "error", "refunded"}


def _normalize_phone(value: str | None) -> str | None:
    if value is None: return None
    normalized = re.sub(r"[\s()-]", "", value.strip())
    return normalized or None


async def _get_or_create_self_recipient(session: AsyncSession, *, user: User):
    email = (user.email or "").strip().lower()
    phone = _normalize_phone(user.phone_number) or ""
    recipient = await get_delivery_recipient_by_fields(
        session,
        user_id=user.id,
        name=user.name,
        surname=user.surname,
        phone=phone,
        email=email,
    )
    if recipient is not None:
        return recipient

    return await create_delivery_recipient(
        session,
        DeliveryRecipientCreate(
            user_id=user.id,
            name=user.name,
            surname=user.surname,
            phone=phone,
            email=email,
        ),
        commit=False,
    )


def _build_image_url(request: Request, *, product: Product | None, variant: Variant | None) -> str:
    if variant is not None and variant.image_path is not None: return build_products_media_url(str(request.base_url), variant.image_path)
    if product is not None and product.image_path is not None: return build_products_media_url(str(request.base_url), product.image_path)
    return build_products_media_url(str(request.base_url), None)


async def _get_products_by_id(session: AsyncSession, product_ids: set[int]) -> dict[int, Product]:
    if not product_ids: return {}
    stmt = select(Product).where(Product.id.in_(product_ids))
    return {product.id: product for product in (await session.execute(stmt)).scalars().all()}


async def _get_variants_by_id(session: AsyncSession, variant_ids: set[int]) -> dict[int, Variant]:
    if not variant_ids:
        return {}
    stmt = select(Variant).options(selectinload(Variant.product)).where(Variant.id.in_(variant_ids))
    return {variant.id: variant for variant in (await session.execute(stmt)).scalars().all()}


async def _clear_order_draft_references(session: AsyncSession, *, draft_id: int) -> None:
    linked_orders = list((await session.execute(select(Order).where(Order.draft_id == draft_id))).scalars().all())
    if not linked_orders:
        return

    for linked_order in linked_orders:
        linked_order.draft = None
        linked_order.draft_id = None

    await session.flush()


def _serialize_order_item(
    request: Request,
    item: OrderItem,
    *,
    products_by_id: dict[int, Product],
    variants_by_id: dict[int, Variant],
) -> OrderItemRead:
    variant = variants_by_id.get(item.variant_id)
    product = products_by_id.get(item.product_id)
    if product is None and variant is not None:
        product = variant.product

    return OrderItemRead(
        id=item.id,
        user_id=item.user_id,
        order_id=item.order_id,
        product_id=item.product_id,
        variant_id=item.variant_id,
        product_name=item.product_name,
        product_sku=item.product_sku,
        variant_name=item.variant_name,
        variant_sku=item.variant_sku,
        quantity=item.quantity,
        unit_price=item.unit_price,
        line_total=item.line_total,
        image_url=_build_image_url(request, product=product, variant=variant),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def serialize_orders(request: Request, session: AsyncSession, orders: list[Order]) -> list[OrderRead]:
    if not orders:
        return []

    product_ids = {item.product_id for order in orders for item in order.items}
    variant_ids = {item.variant_id for order in orders for item in order.items}
    products_by_id = await _get_products_by_id(session, product_ids)
    variants_by_id = await _get_variants_by_id(session, variant_ids)

    serialized_orders: list[OrderRead] = []
    for order in orders:
        serialized_orders.append(
            OrderRead(
                id=order.id,
                order_number=order.order_number,
                draft_id=order.draft_id,
                user_id=order.user_id,
                delivery_address_id=order.delivery_address_id,
                recipient_id=order.recipient_id,
                status=order.status,
                items_count=order.items_count,
                total_quantity=order.total_quantity,
                basket_subtotal=order.basket_subtotal,
                delivery_total=order.delivery_total,
                grand_total=order.grand_total,
                currency=order.currency,
                delivery_period_min=order.delivery_period_min,
                delivery_period_max=order.delivery_period_max,
                comment=order.comment,
                delivery_string=order.delivery_string,
                selected_delivery_service=order.selected_delivery_service,
                selected_delivery_payload=order.selected_delivery_payload,
                checkout_snapshot=order.checkout_snapshot,
                payment_method=order.payment_method,
                payment_provider=order.payment_provider,
                payment_status=order.payment_status,
                payment_invoice_id=order.payment_invoice_id,
                payment_paid_at=order.payment_paid_at,
                payment_error=order.payment_error,
                amocrm_lead_id=order.amocrm_lead_id,
                delivery_created_at=order.delivery_created_at,
                delivery_provider_ref=order.delivery_provider_ref,
                yandex_request_id=order.yandex_request_id,
                is_active=order.is_active,
                is_paid=order.is_paid,
                is_canceled=order.is_canceled,
                is_shipped=order.is_shipped,
                status_code=get_order_status_code(order),
                history_bucket=get_order_history_bucket(order),
                delivery_address=order.delivery_address,
                recipient=order.recipient,
                items=[
                    _serialize_order_item(
                        request,
                        item,
                        products_by_id=products_by_id,
                        variants_by_id=variants_by_id,
                    )
                    for item in order.items
                ],
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
        )

    return serialized_orders


async def serialize_order(request: Request, session: AsyncSession, order: Order) -> OrderRead:
    serialized_orders = await serialize_orders(request, session, [order])
    return serialized_orders[0]


def _delivery_string(selected_delivery_service: str, address_str: str | None) -> str:
    service = (selected_delivery_service or "").strip().upper()
    if not service:
        return "Не указан"
    if address_str:
        return f"{service}: {address_str}"
    return service


def _amocrm_payment_label(payment_method: str | None) -> str:
    method = (payment_method or "").strip().lower()
    if method == "sbp":
        return "IntellectMoney"
    if method == "later":
        return "Оплата позже"
    return payment_method or "Не указан"


def _payment_status_from_step(payment_step: str | None) -> str:
    step = (payment_step or "").strip()
    if step == "OK":
        return "paid"
    if step == "Error":
        return "error"
    if step in PENDING_PAYMENT_STEPS:
        return "pending"
    return step.lower() if step else "pending"


def _payment_status_from_code(payment_status_code: int | None) -> str | None:
    if payment_status_code is None:
        return None
    return PAYMENT_STATUS_BY_CODE.get(int(payment_status_code))


def _parse_payment_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _payment_error_text(payment_status: str | None, payment_step: str | None = None) -> str | None:
    if payment_status == "canceled":
        return "Платеж был отменен"
    if payment_status == "error":
        return "Ошибка оплаты"
    if payment_status == "refunded":
        return "Платеж возвращен"
    if payment_status == "hold":
        return "Платеж захолдирован"
    if payment_status == "partial":
        return "Платеж оплачен частично"
    if payment_step and payment_step not in PENDING_PAYMENT_STEPS:
        return payment_step
    return None


def _order_state_patch_for_amocrm_status(status_id: int) -> dict[str, Any]:
    return {
        "status": amocrm_client.STATUS_WORDS.get(status_id, f"Статус {status_id}"),
        "is_active": status_id not in {143, 142, 82657618},
        "is_paid": status_id in amocrm_client.PAID_STATUS_IDS,
        "is_canceled": status_id in {82657618, 143},
        "is_shipped": status_id in {76566302, 76566306},
    }


def _order_has_state_patch(order: Order, patch: dict[str, Any]) -> bool:
    return all(getattr(order, field) == value for field, value in patch.items())


def _payment_status_to_amocrm_status_id(payment_status: str | None) -> int | None:
    normalized = (payment_status or "").strip().lower()
    if not normalized:
        return None
    if normalized == "paid":
        return amocrm_client.STATUS_IDS["check_paid"]
    if normalized in {"hold", "partial"}:
        return amocrm_client.STATUS_IDS.get("waiting_response")
    if normalized in {"canceled", "error"}:
        return amocrm_client.STATUS_IDS.get("canceled")
    if normalized == "refunded":
        return amocrm_client.STATUS_IDS.get("refund_declined")
    return None


def _base_return_url(request: Request) -> str:
    configured = (APP_PAYMENT_RETURN_BASE_URL or "").strip().rstrip("/")
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def _intellectmoney_urls(request: Request, order_number: int) -> dict[str, str]:
    base = _base_return_url(request)
    api_base = str(request.base_url).rstrip("/")
    fallback_url = f"{base}/payment?orderId={order_number}"
    return {
        "success_url": fallback_url,
        "fail_url": fallback_url,
        "back_url": fallback_url,
        "result_url": f"{api_base}/api/v1/webhooks/intellectmoney",
    }


def _detect_request_ip(request: Request) -> str:
    host = urlsplit(_base_return_url(request)).hostname
    if host:
        try:
            return socket.gethostbyname(host)
        except OSError:
            log.warning("Unable to resolve return base host %s for IntellectMoney; falling back", host)
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def _format_order_for_amocrm(
    order_number: int,
    payload: dict[str, Any],
    delivery_service: str,
    tariff: str | None,
    commentary_text: str,
    delivery_sum: Decimal,
) -> str:
    checkout = payload.get("checkout_data") or {}
    items = checkout.get("items") or []
    delivery = payload.get("selected_delivery") or {}
    contact = payload.get("contact_info") or {}
    address_data = delivery.get("address") or {}
    order_date = datetime.now().strftime("%d.%m.%Y")

    lines_items: list[str] = []
    for idx, item in enumerate(items, start=1):
        name = str(item.get("name") or item.get("product_name") or item.get("feature_name") or "Товар").strip()
        quantity = int(item.get("qty") or 1)
        subtotal = Decimal(str(item.get("subtotal") or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        lines_items.append(f"{idx}. {name} {quantity}шт. — {subtotal}руб.")
    items_block = "\n".join(lines_items) if lines_items else "Товары не указаны."

    items_total = Decimal(str(checkout.get("total") or 0))
    grand_total = items_total + delivery_sum
    service_normalized = (delivery_service or "").strip().upper()
    tariff_normalized = (tariff or "").strip().lower()
    delivery_mode = (delivery.get("deliveryMode") or "").strip()
    postal_code = address_data.get("postal_code") or ""
    formatted_address = address_data.get("formatted") or address_data.get("address") or address_data.get("name") or ""

    if service_normalized == "CDEK":
        if tariff_normalized == "office":
            prefix = "Доставка: Пункт выдачи СДЭК"
        elif tariff_normalized == "door":
            prefix = "Доставка: Курьер СДЭК"
        else:
            prefix = "Доставка: СДЭК"
        delivery_line = f"{prefix}: {postal_code}, {formatted_address}".strip(", ")
    elif service_normalized == "YANDEX":
        if delivery_mode == "self_pickup":
            prefix = "Доставка: Пункт выдачи Яндекс"
        else:
            prefix = "Доставка: Яндекс"
        delivery_line = f"{prefix}: {formatted_address}".strip()
    else:
        delivery_line = f"Доставка: {formatted_address or service_normalized or 'Не указана'}"

    full_name = " ".join(part for part in [contact.get("surname") or "", contact.get("name") or ""] if part).strip() or "Не указано"
    phone = contact.get("phone") or "Не указан"
    email = contact.get("email") or "Не указан"

    return (
        f"Заказ №{order_number} с Приложения\n"
        f"Дата заказа: {order_date}\n"
        f"Cостав заказа:\n"
        f"{items_block}\n\n"
        f"{delivery_line}\n"
        f"Стоимость товаров: {items_total}\n"
        f"Стоимость доставки: {delivery_sum}\n"
        f"Итого к оплате: {grand_total}\n\n"
        f"Имя клиента: {full_name}\n"
        f"Номер телефона: {phone}\n"
        f"Email: {email}\n\n"
        f"Комментарий к заказу: {commentary_text or 'Не указан'}"
    )


def _build_selected_delivery_payload(draft: OrderDraft) -> tuple[str, dict[str, Any]]:
    if draft.delivery_address is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery address is required")

    delivery_address = draft.delivery_address
    address_payload = {
        "code": delivery_address.provider_reference,
        "name": delivery_address.name,
        "address": delivery_address.full_address,
        "formatted": delivery_address.full_address,
        "full_address": delivery_address.full_address,
        "details": delivery_address.details,
        "city": delivery_address.city,
        "postal_code": delivery_address.postal_code,
        "country_code": delivery_address.country_code,
        "latitude": delivery_address.latitude,
        "longitude": delivery_address.longitude,
        "provider_reference": delivery_address.provider_reference,
    }
    delivery_total = float(draft.delivery_total)

    if delivery_address.provider == "CDEK":
        delivery_mode = "office" if delivery_address.mode == "pickup" else "door"
        payload = {
            "deliveryMode": delivery_mode,
            "tariff": {
                "tariff_code": get_cdek_client().tariff_codes[delivery_mode],
                "tariff_name": delivery_mode,
                "delivery_sum": delivery_total,
            },
            "address": address_payload,
            "delivery_sum": delivery_total,
        }
        return "CDEK", payload

    if delivery_address.provider == "YANDEX":
        if delivery_address.mode != "pickup":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Yandex door delivery is not supported in this flow")
        payload = {
            "deliveryMode": "self_pickup",
            "tariff": {
                "tariff_name": "self_pickup",
            },
            "address": address_payload,
            "delivery_sum": delivery_total,
        }
        return "YANDEX", payload

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported delivery provider")


def _build_checkout_snapshot(draft: OrderDraft, *, payment_method: str, selected_delivery_service: str, selected_delivery_payload: dict[str, Any]) -> dict[str, Any]:
    if draft.recipient is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Recipient is required")

    items = [
        {
            "id": item.product_id,
            "featureId": item.variant_id,
            "name": item.product_name,
            "product_name": item.product_name,
            "feature_name": item.variant_name,
            "code": item.product_sku,
            "qty": item.quantity,
            "price": float(item.unit_price),
            "subtotal": float(item.line_total),
        }
        for item in draft.items
    ]

    return {
        "source": "shop_application",
        "payment_method": payment_method,
        "contact_info": {
            "name": draft.recipient.name,
            "surname": draft.recipient.surname,
            "phone": draft.recipient.phone,
            "email": draft.recipient.email,
        },
        "checkout_data": {
            "items": items,
            "total": float(draft.basket_subtotal),
        },
        "selected_delivery": deepcopy(selected_delivery_payload),
        "selected_delivery_service": selected_delivery_service,
        "commentary": draft.comment or "Не указан",
        "order_date": datetime.now(timezone.utc).isoformat(),
    }


async def ensure_order_has_amocrm_lead(session: AsyncSession, order: Order, *, user: User) -> int:
    if order.amocrm_lead_id:
        return int(order.amocrm_lead_id)

    existing_lead = await amocrm_client.find_lead_by_order_number(order.order_number)
    if existing_lead is not None:
        order.amocrm_lead_id = int(existing_lead["id"])
        await session.flush()
        return int(order.amocrm_lead_id)

    if order.recipient is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Recipient is required")

    lead_name = " ".join(part for part in [order.recipient.name, order.recipient.surname] if part).strip() or f"Заказ #{order.order_number}"
    phone = _normalize_phone(order.recipient.phone) or _normalize_phone(user.phone_number) or order.recipient.phone
    email = (order.recipient.email or user.email or "").strip().lower() or None
    contact = await amocrm_client.find_or_create_contact(
        lead_name=lead_name,
        phone=phone,
        email=email,
        contact_id=user.contact_id,
    )
    contact_id = contact.get("id") if isinstance(contact, dict) else None
    if contact_id and contact_id != user.contact_id:
        user.contact_id = int(contact_id)

    address_str = normalize_address_for_cf((order.selected_delivery_payload or {}).get("address")) or order.delivery_string or "Не указан"
    tariff = (
        (order.selected_delivery_payload or {}).get("deliveryMode")
        or ((order.selected_delivery_payload or {}).get("tariff") or {}).get("tariff_name")
        or ((order.selected_delivery_payload or {}).get("tariff") or {}).get("tariff_code")
    )
    note_text = _format_order_for_amocrm(
        order.order_number,
        order.checkout_snapshot or {},
        order.selected_delivery_service,
        tariff,
        order.comment or "Не указан",
        order.delivery_total,
    )
    lead = await amocrm_client.create_lead_with_contact_and_note(
        lead_name=lead_name,
        price=int(order.grand_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        address_str=address_str,
        phone=phone,
        email=email,
        order_number=str(order.order_number),
        delivery_service=order.selected_delivery_service,
        note_text=note_text,
        payment_method=_amocrm_payment_label(order.payment_method),
        status_id=amocrm_client.STATUS_IDS["main"],
        delivery_sum=order.delivery_total,
        contact_id=int(contact_id) if contact_id else None,
    )
    order.amocrm_lead_id = int(lead["id"])
    await session.flush()
    return int(order.amocrm_lead_id)


async def create_order_from_draft_for_user(
    session: AsyncSession,
    *,
    request: Request,
    user: User,
    draft_id: int,
    payment_method: str,
) -> Order:
    draft = await get_order_draft_by_id(session, draft_id, user_id=user.id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")

    existing_order = await get_order_by_draft_id(session, draft.id, user_id=user.id)
    if existing_order is not None:
        await _clear_order_draft_references(session, draft_id=draft.id)
        await delete_order_draft(session, draft, commit=False)
        await session.commit()

        refreshed_order = await get_order_by_id(session, existing_order.id, user_id=user.id)
        if refreshed_order is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load existing order")
        return refreshed_order

    if draft.recipient is None:
        recipient = await _get_or_create_self_recipient(session, user=user)
        draft.recipient_id = recipient.id
        draft.recipient = recipient
        await session.flush()
    if draft.delivery_address is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery address is required")
    if not draft.items:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order draft is empty")

    selected_delivery_service, selected_delivery_payload = _build_selected_delivery_payload(draft)
    checkout_snapshot = _build_checkout_snapshot(
        draft,
        payment_method=payment_method,
        selected_delivery_service=selected_delivery_service,
        selected_delivery_payload=selected_delivery_payload,
    )
    delivery_string = _delivery_string(
        selected_delivery_service,
        normalize_address_for_cf(selected_delivery_payload.get("address")),
    )

    order = await create_order(
        session,
        OrderCreate(
            draft_id=None,
            user_id=user.id,
            delivery_address_id=draft.delivery_address_id,
            recipient_id=draft.recipient_id,
            status=amocrm_client.STATUS_WORDS.get(amocrm_client.STATUS_IDS["main"], "Создан"),
            items_count=draft.items_count,
            total_quantity=draft.total_quantity,
            basket_subtotal=draft.basket_subtotal,
            delivery_total=draft.delivery_total,
            grand_total=draft.grand_total,
            currency=draft.currency,
            delivery_period_min=draft.delivery_period_min,
            delivery_period_max=draft.delivery_period_max,
            comment=draft.comment,
            delivery_string=delivery_string,
            selected_delivery_service=selected_delivery_service,
            selected_delivery_payload=selected_delivery_payload,
            checkout_snapshot=checkout_snapshot,
            payment_method=payment_method,
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

    order_items = [
        OrderItem(
            user_id=user.id,
            order_id=order.id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            product_name=item.product_name,
            product_sku=item.product_sku,
            variant_name=item.variant_name,
            variant_sku=item.variant_sku,
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=item.line_total,
        )
        for item in draft.items
    ]
    session.add_all(order_items)
    await session.flush()
    for item in draft.items:
        await record_purchase(
            session,
            user_id=user.id,
            product_id=item.product_id,
            quantity=item.quantity,
            commit=False,
        )
    await ensure_order_has_amocrm_lead(session, order, user=user)
    await _clear_order_draft_references(session, draft_id=draft.id)
    await delete_order_draft(session, draft, commit=False)
    await session.commit()

    created_order = await get_order_by_id(session, order.id, user_id=user.id)
    if created_order is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order")

    return created_order


async def get_order_for_user(session: AsyncSession, *, user_id: int, order_id: int) -> Order | None:
    return await get_order_by_id(session, order_id, user_id=user_id)


async def get_orders_history_for_user(
    session: AsyncSession,
    *,
    user_id: int,
    history_bucket: OrderHistoryBucket | None = None,
    status_code: OrderStatusCode | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Order]:
    return await get_orders_for_user_crud(
        session,
        user_id,
        history_bucket=history_bucket,
        status_code=status_code,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


def _payment_status_payload(
    order: Order,
    *,
    payment_step: str | None = None,
    qr_url: str | None = None,
    qr_image: str | None = None,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    payload = {
        "status": "success",
        "order_id": order.id,
        "order_number": order.order_number,
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "payment_step": payment_step,
        "invoice_id": order.payment_invoice_id,
        "qr_url": qr_url,
        "qr_image": qr_image,
        "is_paid": bool(order.is_paid or order.payment_status == "paid"),
        "can_retry": order.payment_status in {"canceled", "error"},
    }
    if expires_at is not None:
        payload["expires_at"] = expires_at.replace(microsecond=0).isoformat()
    return payload


async def _resolve_payment_qr_image(
    request: Request,
    order: Order,
    *,
    qr_image: str | None,
    qr_url: str | None,
) -> str | None:
    try:
        saved_path = await save_order_payment_qr(
            order.user_id,
            order.id,
            qr_image=qr_image,
            qr_url=qr_url,
        )
    except Exception:
        log.exception("Failed to save SBP QR for order %s", order.order_number)
        saved_path = find_order_payment_qr_path(order.user_id, order.id)

    return build_order_payment_qr_url(request, saved_path)


async def _move_lead_to_pending_payment(session: AsyncSession, order: Order) -> Order:
    pending_status_id = amocrm_client.STATUS_IDS.get("pending_payment")
    if not order.amocrm_lead_id or pending_status_id is None:
        return order

    pending_patch = _order_state_patch_for_amocrm_status(pending_status_id)
    if _order_has_state_patch(order, pending_patch):
        return order

    previous_status = order.status

    try:
        await amocrm_client.update_lead_status(int(order.amocrm_lead_id), pending_status_id)
    except Exception:
        log.exception("Failed to update amoCRM lead %s to pending payment status", order.amocrm_lead_id)
        return order

    updated_order = await update_order(
        session,
        order,
        OrderUpdate(**pending_patch),
        commit=True,
    )
    await send_order_status_change_notification_if_needed(session, previous_status=previous_status, order=updated_order)
    return updated_order


async def _move_lead_to_payment_result_status(
    session: AsyncSession,
    order: Order,
    *,
    payment_status: str | None,
) -> Order:
    target_status_id = _payment_status_to_amocrm_status_id(payment_status)
    if not order.amocrm_lead_id or target_status_id is None:
        return order

    target_patch = _order_state_patch_for_amocrm_status(target_status_id)
    if _order_has_state_patch(order, target_patch):
        return order

    previous_status = order.status

    try:
        await amocrm_client.update_lead_status(int(order.amocrm_lead_id), target_status_id)
    except Exception:
        log.exception(
            "Failed to update amoCRM lead %s for payment status %s",
            order.amocrm_lead_id,
            payment_status,
        )
        return order

    updated_order = await update_order(
        session,
        order,
        OrderUpdate(**target_patch),
        commit=True,
    )
    await send_order_status_change_notification_if_needed(session, previous_status=previous_status, order=updated_order)
    return updated_order


async def reconcile_sbp_payment(
    session: AsyncSession,
    order: Order,
    *,
    payment_step: str | None = None,
    payment_status_code: int | None = None,
    payment_data: str | None = None,
    invoice_id: str | None = None,
) -> Order:
    payment_status = _payment_status_from_code(payment_status_code) or _payment_status_from_step(payment_step)
    patch: dict[str, Any] = {}
    if invoice_id:
        patch["payment_invoice_id"] = str(invoice_id)

    if payment_status == "paid":
        order = await _move_lead_to_payment_result_status(session, order, payment_status=payment_status)
        patch["payment_status"] = "paid"
        patch["payment_paid_at"] = _parse_payment_timestamp(payment_data) or datetime.now(timezone.utc)
        patch["payment_error"] = ""
    else:
        if payment_status in {"canceled", "error", "refunded", "hold", "partial"}:
            order = await _move_lead_to_payment_result_status(session, order, payment_status=payment_status)
        patch["payment_status"] = payment_status
        error_text = _payment_error_text(payment_status, payment_step)
        if error_text:
            patch["payment_error"] = error_text

    updated_order = await update_order(session, order, OrderUpdate(**patch), commit=True)
    return updated_order


async def create_payment_for_order(session: AsyncSession, *, request: Request, order: Order) -> dict[str, Any]:
    payment_method = (order.payment_method or "later").strip().lower()
    if payment_method == "later":
        order = await update_order(
            session,
            order,
            OrderUpdate(
                payment_method="later",
                payment_provider="manager",
                payment_status="pending",
                payment_error="",
            ),
            commit=True,
        )
        return _payment_status_payload(order)

    if payment_method != "sbp":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported payment method")

    urls = _intellectmoney_urls(request, order.order_number)
    ip_address = _detect_request_ip(request)
    user_name = " ".join(part for part in [order.recipient.name, order.recipient.surname] if part).strip() or f"Заказ {order.order_number}"
    order = await update_order(
        session,
        order,
        OrderUpdate(
            payment_method="sbp",
            payment_provider="intellectmoney",
            payment_status="created",
            payment_error="",
        ),
        commit=True,
    )

    try:
        expires_at = datetime.now() + timedelta(minutes=30)
        create_invoice_result = await intellectmoney.create_invoice(
            order_id=str(order.order_number),
            service_name=f"Заказ №{order.order_number}",
            amount_rub=order.grand_total,
            user_name=user_name,
            email=order.recipient.email,
            success_url=urls["success_url"],
            fail_url=urls["fail_url"],
            back_url=urls["back_url"],
            result_url=urls["result_url"],
            preference="Sbp",
        )

        result_payload = create_invoice_result.get("Result") or {}
        invoice_id = str(
            result_payload.get("InvoiceId")
            or result_payload.get("invoiceId")
            or create_invoice_result.get("InvoiceId")
            or ""
        )
        if not invoice_id:
            raise IntellectMoneyError("IntellectMoney createInvoice succeeded without InvoiceId")

        order = await update_order(session, order, OrderUpdate(payment_invoice_id=invoice_id), commit=True)
        sbp_result = await intellectmoney.sbp_payment(
            invoice_id=invoice_id,
            success_url=urls["success_url"],
            fail_url=urls["fail_url"],
            ip_address=ip_address,
        )
        parsed_sbp = intellectmoney.parse_payment_state(sbp_result)
        state_result = await intellectmoney.get_bank_card_payment_state(invoice_id=invoice_id)
        parsed_state = intellectmoney.parse_payment_state(state_result)
        payment_step = parsed_state["payment_step"] or parsed_sbp["payment_step"]
        qr_url = parsed_state["qr_url"] or parsed_sbp["qr_url"]
        qr_image = parsed_state["qr_image"] or parsed_sbp["qr_image"]
        saved_qr_image = await _resolve_payment_qr_image(
            request,
            order,
            qr_image=qr_image,
            qr_url=qr_url,
        )

        if payment_step not in PENDING_PAYMENT_STEPS:
            order = await reconcile_sbp_payment(
                session,
                order,
                payment_step=payment_step,
                invoice_id=invoice_id,
            )
        else:
            order = await update_order(
                session,
                order,
                OrderUpdate(payment_status=_payment_status_from_step(payment_step)),
                commit=True,
            )
            if saved_qr_image or qr_image or qr_url:
                order = await _move_lead_to_pending_payment(session, order)

        return _payment_status_payload(
            order,
            payment_step=payment_step,
            qr_url=qr_url,
            qr_image=saved_qr_image or qr_image,
            expires_at=expires_at,
        )
    except IntellectMoneyError as exc:
        await update_order(session, order, OrderUpdate(payment_status="error", payment_error=str(exc)), commit=True)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("Failed to initialize SBP payment for order %s", order.order_number)
        await update_order(
            session,
            order,
            OrderUpdate(payment_status="error", payment_error="Не удалось инициализировать СБП"),
            commit=True,
        )
        raise HTTPException(status_code=502, detail="Failed to initialize SBP payment") from exc


async def get_payment_status_for_order(session: AsyncSession, *, request: Request, order: Order) -> dict[str, Any]:
    payment_step = None
    qr_url = None
    qr_image = None

    if (
        (order.payment_method or "").lower() == "sbp"
        and order.payment_invoice_id
        and (order.payment_status or "") not in FINAL_PAYMENT_STATUSES
    ):
        try:
            state_result = await intellectmoney.get_bank_card_payment_state(invoice_id=str(order.payment_invoice_id))
            parsed_state = intellectmoney.parse_payment_state(state_result)
            payment_step = parsed_state["payment_step"]
            qr_url = parsed_state["qr_url"]
            qr_image = parsed_state["qr_image"]
            if payment_step:
                order = await reconcile_sbp_payment(
                    session,
                    order,
                    payment_step=payment_step,
                    invoice_id=str(order.payment_invoice_id),
                )
                if payment_step in PENDING_PAYMENT_STEPS:
                    order = await update_order(
                        session,
                        order,
                        OrderUpdate(payment_status=_payment_status_from_step(payment_step)),
                        commit=True,
                    )
        except IntellectMoneyError as exc:
            log.warning("IntellectMoney status check failed for order %s: %s", order.order_number, exc)

    saved_qr_image = await _resolve_payment_qr_image(
        request,
        order,
        qr_image=qr_image,
        qr_url=qr_url,
    )
    if payment_step in PENDING_PAYMENT_STEPS and (saved_qr_image or qr_image or qr_url):
        order = await _move_lead_to_pending_payment(session, order)
    return _payment_status_payload(
        order,
        payment_step=payment_step,
        qr_url=qr_url,
        qr_image=saved_qr_image or qr_image,
    )


async def apply_amocrm_status_update(session: AsyncSession, *, order: Order, status_id: int) -> Order:
    previous_status = order.status
    order = await update_order(
        session,
        order,
        OrderUpdate(**_order_state_patch_for_amocrm_status(status_id)),
        commit=False,
    )

    if status_id in amocrm_client.PAID_STATUS_IDS and order.delivery_created_at is None:
        delivery_patch = await create_delivery_for_order(order)
        if delivery_patch:
            delivery_patch["delivery_created_at"] = datetime.now(timezone.utc)
            order = await update_order(session, order, OrderUpdate(**delivery_patch), commit=False)

    await session.commit()
    refreshed_order = await get_order_by_id(session, order.id)
    if refreshed_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reload order after amoCRM update")
    await send_order_status_change_notification_if_needed(session, previous_status=previous_status, order=refreshed_order)
    return refreshed_order
