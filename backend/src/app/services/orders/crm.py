import logging

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.services.push_notifications import send_order_status_change_notification_if_needed
from src.database.crud import get_order_by_id, update_order
from src.database.models import Order, User
from src.database.schemas import OrderUpdate
from src.integrations.amocrm import amocrm_client

from .common import _normalize_phone
from .fulfillment import create_delivery_for_order, normalize_address_for_cf

log = logging.getLogger(__name__)


def _amocrm_payment_label(payment_method: str | None) -> str:
    method = (payment_method or "").strip().lower()
    if method == "sbp": return "IntellectMoney"
    if method == "later": return "Оплата позже"
    return payment_method or "Не указан"

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
    if not normalized: return None
    if normalized == "paid": return amocrm_client.STATUS_IDS["check_paid"]
    if normalized in {"hold", "partial"}: return amocrm_client.STATUS_IDS.get("waiting_response")
    if normalized in {"canceled", "error"}: return amocrm_client.STATUS_IDS.get("canceled")
    if normalized == "refunded": return amocrm_client.STATUS_IDS.get("refund_declined")
    return None

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

async def ensure_order_has_amocrm_lead(session: AsyncSession, order: Order, *, user: User) -> int:
    if order.amocrm_lead_id: return int(order.amocrm_lead_id)

    existing_lead = await amocrm_client.find_lead_by_order_number(order.order_number)
    if existing_lead is not None:
        order.amocrm_lead_id = int(existing_lead["id"])
        await session.flush()
        return int(order.amocrm_lead_id)

    if order.recipient is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Recipient is required")
    lead_name = " ".join(part for part in [order.recipient.name, order.recipient.surname] if part).strip() or f"Заказ #{order.order_number}"
    phone = _normalize_phone(order.recipient.phone) or _normalize_phone(user.phone_number) or order.recipient.phone
    email = (order.recipient.email or user.email or "").strip().lower() or None
    contact = await amocrm_client.find_or_create_contact(lead_name=lead_name, phone=phone, email=email, contact_id=user.contact_id)
    contact_id = contact.get("id") if isinstance(contact, dict) else None
    if contact_id and contact_id != user.contact_id: user.contact_id = int(contact_id)

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

async def _move_lead_to_pending_payment(session: AsyncSession, order: Order) -> Order:
    pending_status_id = amocrm_client.STATUS_IDS.get("pending_payment")
    if not order.amocrm_lead_id or pending_status_id is None: return order

    pending_patch = _order_state_patch_for_amocrm_status(pending_status_id)
    if _order_has_state_patch(order, pending_patch): return order

    previous_status = order.status

    try: await amocrm_client.update_lead_status(int(order.amocrm_lead_id), pending_status_id)
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
    if not order.amocrm_lead_id or target_status_id is None: return order

    target_patch = _order_state_patch_for_amocrm_status(target_status_id)
    if _order_has_state_patch(order, target_patch): return order

    previous_status = order.status

    try: await amocrm_client.update_lead_status(int(order.amocrm_lead_id), target_status_id)
    except Exception:
        log.exception(
            "Failed to update amoCRM lead %s for payment status %s",
            order.amocrm_lead_id,
            payment_status,
        )
        return order

    updated_order = await update_order(session, order, OrderUpdate(**target_patch), commit=True)
    await send_order_status_change_notification_if_needed(session, previous_status=previous_status, order=updated_order)
    return updated_order

async def apply_amocrm_status_update(session: AsyncSession, *, order: Order, status_id: int) -> Order:
    previous_status = order.status
    order = await update_order(session, order, OrderUpdate(**_order_state_patch_for_amocrm_status(status_id)), commit=False)

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
