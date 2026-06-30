from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import logging
import secrets
from types import SimpleNamespace
from typing import Any
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from config import ufa_now
from src.app.services.benefits.money import quantize_money
from src.app.services.benefits.service import resolve_benefits_for_user
from src.app.services.discounts import discountable_subtotal_for_lines
from src.app.services.recommendations import record_purchase
from src.database.crud import create_delivery_recipient, create_order, create_order_draft, delete_order_draft, get_basket_by_user_id, get_delivery_recipient_by_fields, get_order_by_code, get_order_by_draft_id, get_order_by_id, get_order_draft_by_id, get_orders_for_user as get_orders_for_user_crud
from src.database.models import BasketItem, Order, OrderBenefitApplication, OrderDraft, OrderDraftItem, OrderItem, User, Variant
from src.database.models.orders.history import OrderHistoryBucket, OrderStatusCode, get_order_history_bucket
from src.database.schemas import DeliveryRecipientCreate, OrderCreate, OrderDraftCreate
from src.integrations.amocrm import get_amocrm_client
from src.integrations.delivery.cdek import get_cdek_client
from src.integrations.delivery.geo import get_geo_client
from src.integrations.delivery.schemas import COUNTRY_NAMES
from src.integrations.moysklad.order_sync import sync_order_to_moysklad_safe
from src.normalize import optional_str

from .common import _delivery_string, _normalize_phone
from .crm import ensure_order_has_amocrm_lead
from .fulfillment_payloads import normalize_address_for_cf

ORDER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
amocrm_client = get_amocrm_client()
log = logging.getLogger(__name__)


async def _generate_order_code(session: AsyncSession) -> str:
    for _ in range(20):
        suffix = "".join(secrets.choice(ORDER_CODE_ALPHABET) for _ in range(8))
        order_code = f"EP-{suffix}"
        if await get_order_by_code(session, order_code) is None: return order_code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate order code")


async def _get_or_create_self_recipient(session: AsyncSession, *, user: User):
    phone = _normalize_phone(user.phone_number) or ""
    email = (user.email or "").strip().lower()
    recipient = await get_delivery_recipient_by_fields(session, user_id=user.id, name=user.name, surname=user.surname, phone=phone, email=email)
    if recipient is not None:
        return recipient
    return await create_delivery_recipient(session, DeliveryRecipientCreate(user_id=user.id, name=user.name, surname=user.surname, phone=phone, email=email), commit=False)


async def _clear_order_draft_references(session: AsyncSession, *, draft_id: int) -> None:
    linked_orders = list((await session.execute(select(Order).where(Order.draft_id == draft_id))).scalars().all())
    if not linked_orders:
        return

    for linked_order in linked_orders:
        linked_order.draft = None
        linked_order.draft_id = None

    await session.flush()

def _country_name_from_code(country_code: Any) -> str | None:
    normalized_country_code = optional_str(country_code)
    if not normalized_country_code:
        return None
    return COUNTRY_NAMES.get(normalized_country_code.upper())  # type: ignore[arg-type]


def _geocode_query(address_payload: dict[str, Any]) -> str | None:
    latitude = address_payload.get("latitude")
    longitude = address_payload.get("longitude")
    if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
        return f"{float(longitude):.6f},{float(latitude):.6f}"

    return (
        optional_str(address_payload.get("full_address"))
        or optional_str(address_payload.get("formatted"))
        or optional_str(address_payload.get("address"))
    )


async def _enrich_selected_delivery_address_payload(address_payload: dict[str, Any]) -> None:
    country_name = (
        optional_str(address_payload.get("country"))
        or _country_name_from_code(address_payload.get("country_code"))
    )
    if country_name:
        address_payload["country"] = country_name

    if all(
        optional_str(address_payload.get(field_name))
        for field_name in ("city", "postal_code", "street", "house", "region")
    ):
        return

    query = _geocode_query(address_payload)
    if not query:
        return

    try:
        geocode_result = await get_geo_client().geocode(address=query, lang="ru_RU", results=1)
    except Exception:
        log.warning("Failed to geocode delivery address payload query=%s", query, exc_info=True)
        return

    if optional_str(address_payload.get("city")) is None and geocode_result.city:
        address_payload["city"] = geocode_result.city
    if optional_str(address_payload.get("postal_code")) is None and geocode_result.postal_code:
        address_payload["postal_code"] = geocode_result.postal_code
    if optional_str(address_payload.get("country_code")) is None and geocode_result.country_code:
        address_payload["country_code"] = geocode_result.country_code
    if optional_str(address_payload.get("country")) is None and geocode_result.country:
        address_payload["country"] = geocode_result.country
    if optional_str(address_payload.get("region")) is None and geocode_result.region:
        address_payload["region"] = geocode_result.region
    if optional_str(address_payload.get("street")) is None and geocode_result.street:
        address_payload["street"] = geocode_result.street
    if optional_str(address_payload.get("house")) is None and geocode_result.house:
        address_payload["house"] = geocode_result.house


async def _build_selected_delivery_payload(draft: OrderDraft) -> tuple[str, dict[str, Any]]:
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
    await _enrich_selected_delivery_address_payload(address_payload)
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
            "tariff": {"tariff_name": "self_pickup"},
            "address": address_payload,
            "delivery_sum": delivery_total,
        }
        return "YANDEX", payload

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported delivery provider")


def _json_money(value: Any) -> float:
    return float(quantize_money(value) or Decimal("0.00"))


def _json_safe_benefits(resolved_benefits: dict[str, Any] | None) -> dict[str, Any]:
    if resolved_benefits is None:
        return {}

    return {
        "entered_code": resolved_benefits.get("entered_code"),
        "basket_subtotal": _json_money(resolved_benefits.get("basket_subtotal")),
        "stacked_discount_amount": _json_money(resolved_benefits.get("stacked_discount_amount")),
        "total_after_discounts": _json_money(resolved_benefits.get("total_after_discounts")),
        "applications": [
            {
                "source_kind": option.get("source_kind"),
                "code": option.get("code"),
                "discount_percent": str(option.get("discount_percent")) if option.get("discount_percent") is not None else None,
                "discount_amount": str(option.get("applied_discount_amount")) if option.get("applied_discount_amount") is not None else None,
                "sequence": option.get("sequence"),
            }
            for option in resolved_benefits.get("stacked_discount_options", [])
        ],
    }


def _checkout_snapshot_item(item) -> dict[str, Any]:
    return {
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


def _build_checkout_snapshot(draft: OrderDraft, *, payment_method: str, selected_delivery_service: str, selected_delivery_payload: dict[str, Any], resolved_benefits: dict[str, Any] | None = None) -> dict[str, Any]:
    if draft.recipient is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Recipient is required")
    items = [_checkout_snapshot_item(item) for item in draft.items]
    return {
        "source": "shop_application",
        "payment_method": payment_method,
        "contact_info": {
            "name": draft.recipient.name,
            "surname": draft.recipient.surname,
            "phone": draft.recipient.phone,
            "email": draft.recipient.email,
        },
        "checkout_data": {"items": items, "total": float(draft.basket_subtotal)},
        "benefits": _json_safe_benefits(resolved_benefits),
        "selected_delivery": deepcopy(selected_delivery_payload),
        "selected_delivery_service": selected_delivery_service,
        "commentary": draft.comment or "Не указан",
        "order_date": datetime.now(timezone.utc).isoformat(),
    }


async def _persist_order_benefit_applications(session: AsyncSession, *, order: Order, user: User, resolved_benefits: dict[str, Any]) -> None:
    now = ufa_now()
    applications: list[OrderBenefitApplication] = []

    for option in resolved_benefits.get("stacked_discount_options", []):
        source_kind = option.get("source_kind")
        source_record_id = option.get("source_record_id")
        kwargs: dict[str, Any] = {}
        if source_kind == "app_referral":
            kwargs["referral_profile_id"] = source_record_id

        snapshot = {
            "sequence": option.get("sequence"),
            "subtotal_before": str(option.get("subtotal_before")),
            "subtotal_after": str(option.get("subtotal_after")),
            "entered_code": resolved_benefits.get("entered_code"),
        }
        if source_kind == "app_referral":
            snapshot.update(
                {
                    "promo_code": option.get("code"),
                }
            )

        applications.append(
            OrderBenefitApplication(
                order_id=order.id,
                user_id=user.id,
                source_kind=source_kind,
                entered_code=resolved_benefits.get("entered_code"),
                resolved_code=option.get("code"),
                discount_percent=option.get("discount_percent"),
                discount_amount=option.get("applied_discount_amount"),
                currency=option.get("currency") or resolved_benefits.get("currency") or order.currency,
                status="applied",
                applied_at=now,
                calculation_snapshot=snapshot,
                **kwargs,
            )
        )

    if applications:
        session.add_all(applications)
        await session.flush()


async def _resolve_checkout_benefits(session: AsyncSession, *, user: User, subtotal: Decimal, discountable_subtotal: Decimal, currency: str, entered_code: str | None) -> dict[str, Any]:
    return await resolve_benefits_for_user(
        session,
        user=user,
        entered_code=entered_code,
        subtotal=subtotal,
        discountable_subtotal=discountable_subtotal,
        currency=currency,
    )


def _build_order_create_data(*, user_id: int, delivery_address_id: int, recipient_id: int, order_code: str, items_count: int, total_quantity: int, basket_subtotal: Decimal, delivery_total: Decimal, grand_total: Decimal, currency: str, delivery_period_min: int | None, delivery_period_max: int | None, comment: str | None, delivery_string: str, selected_delivery_service: str, selected_delivery_payload: dict[str, Any], checkout_snapshot: dict[str, Any], payment_method: str) -> OrderCreate:
    payment_status = "pending" if payment_method.strip().lower() == "later" else "draft"
    return OrderCreate(
        draft_id=None,
        user_id=user_id,
        delivery_address_id=delivery_address_id,
        recipient_id=recipient_id,
        order_code=order_code,
        status=amocrm_client.STATUS_WORDS.get(amocrm_client.STATUS_IDS["main"], "Создан"),
        items_count=items_count,
        total_quantity=total_quantity,
        basket_subtotal=basket_subtotal,
        delivery_total=delivery_total,
        grand_total=grand_total,
        currency=currency,
        delivery_period_min=delivery_period_min,
        delivery_period_max=delivery_period_max,
        comment=comment,
        delivery_string=delivery_string,
        selected_delivery_service=selected_delivery_service,
        selected_delivery_payload=selected_delivery_payload,
        checkout_snapshot=checkout_snapshot,
        payment_method=payment_method,
        payment_provider=None,
        payment_status=payment_status,
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
    )


def _build_order_item_from_draft_item(*, user_id: int, order_id: int, item) -> OrderItem:
    return OrderItem(
        user_id=user_id,
        order_id=order_id,
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


def _build_order_item_from_basket_row(*, user_id: int, order_id: int, row: tuple[BasketItem, Decimal, Decimal]) -> OrderItem:
    item, unit_price, line_total = row
    return OrderItem(
        user_id=user_id,
        order_id=order_id,
        product_id=item.product_id,
        variant_id=item.variant_id,
        product_name=item.product.name,
        product_sku=item.product.sku,
        variant_name=item.variant.name,
        variant_sku=item.variant.sku,
        quantity=item.quantity,
        unit_price=unit_price,
        line_total=line_total,
    )


async def create_order_from_draft_for_user(session: AsyncSession, *, user: User, draft_id: int, payment_method: str, entered_code: str | None = None) -> Order:
    user_id = int(user.__dict__.get("id") or user.id)
    draft = await get_order_draft_by_id(session, draft_id, user_id=user_id)
    if draft is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")

    existing_order = await get_order_by_draft_id(session, draft.id, user_id=user_id)
    if existing_order is not None:
        await _clear_order_draft_references(session, draft_id=draft.id)
        await delete_order_draft(session, draft, commit=False)
        await session.commit()

        refreshed_order = await get_order_by_id(session, existing_order.id, user_id=user_id)
        if refreshed_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load existing order")
        return refreshed_order

    if draft.recipient is None:
        recipient = await _get_or_create_self_recipient(session, user=user)
        draft.recipient_id = recipient.id
        draft.recipient = recipient
        await session.flush()

    if draft.delivery_address is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery address is required")
    if not draft.items: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order draft is empty")

    selected_delivery_service, selected_delivery_payload = await _build_selected_delivery_payload(draft)
    discountable_subtotal = await discountable_subtotal_for_lines(
        session,
        ((item.product_id, item.line_total) for item in draft.items),
    )
    resolved_benefits = await _resolve_checkout_benefits(
        session,
        user=user,
        subtotal=draft.basket_subtotal,
        discountable_subtotal=discountable_subtotal,
        currency=draft.currency,
        entered_code=entered_code,
    )
    grand_total = (quantize_money(resolved_benefits["total_after_discounts"]) or Decimal("0.00")) + draft.delivery_total
    checkout_snapshot = _build_checkout_snapshot(
        draft,
        payment_method=payment_method,
        selected_delivery_service=selected_delivery_service,
        selected_delivery_payload=selected_delivery_payload,
        resolved_benefits=resolved_benefits,
    )
    delivery_string = _delivery_string(selected_delivery_service, normalize_address_for_cf(selected_delivery_payload.get("address")))

    order_code = await _generate_order_code(session)
    order_create = _build_order_create_data(
        user_id=user_id,
        delivery_address_id=draft.delivery_address_id,
        recipient_id=draft.recipient_id,
        order_code=order_code,
        items_count=draft.items_count,
        total_quantity=draft.total_quantity,
        basket_subtotal=draft.basket_subtotal,
        delivery_total=draft.delivery_total,
        grand_total=grand_total,
        currency=draft.currency,
        delivery_period_min=draft.delivery_period_min,
        delivery_period_max=draft.delivery_period_max,
        comment=draft.comment,
        delivery_string=delivery_string,
        selected_delivery_service=selected_delivery_service,
        selected_delivery_payload=selected_delivery_payload,
        checkout_snapshot=checkout_snapshot,
        payment_method=payment_method,
    )
    order = await create_order(session, order_create, commit=False)
    order_items = [_build_order_item_from_draft_item(user_id=user_id, order_id=order.id, item=item) for item in draft.items]
    session.add_all(order_items)
    await session.flush()
    await _persist_order_benefit_applications(session, order=order, user=user, resolved_benefits=resolved_benefits)
    for item in draft.items: await record_purchase(session, user_id=user_id, product_id=item.product_id, quantity=item.quantity, commit=False)
    await ensure_order_has_amocrm_lead(session, order, user=user)
    await _clear_order_draft_references(session, draft_id=draft.id)
    await delete_order_draft(session, draft, commit=False)
    await session.commit()

    created_order = await get_order_by_id(session, order.id, user_id=user_id)
    if created_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order")
    created_order_id = int(order.__dict__.get("id") or created_order.__dict__.get("id") or created_order.id)
    await sync_order_to_moysklad_safe(session, order=created_order, user=user)
    reloaded_order = await get_order_by_id(session, created_order_id, user_id=user_id)
    if reloaded_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order")
    return reloaded_order


async def create_order_from_basket_for_user(session: AsyncSession, *, user: User, payment_method: str, entered_code: str | None = None) -> Order:
    user_id = int(user.__dict__.get("id") or user.id)
    basket = await get_basket_by_user_id(session, user_id)
    if basket is None or not basket.items: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Basket is empty")
    if basket.delivery_address is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery address is required")

    if basket.recipient is None:
        recipient = await _get_or_create_self_recipient(session, user=user)
        basket.recipient_id = recipient.id
        basket.recipient = recipient
        await session.flush()

    basket_subtotal = Decimal("0.00")
    total_quantity = 0
    snapshot_items = []
    order_item_rows: list[tuple[BasketItem, Decimal, Decimal]] = []

    for basket_item in basket.items:
        variant = basket_item.variant
        if variant is None or variant.archived or variant.stock <= 0 or basket_item.quantity > variant.stock:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Basket contains unavailable items")

        unit_price = variant.price
        line_total = unit_price * basket_item.quantity
        basket_subtotal += line_total
        total_quantity += basket_item.quantity
        order_item_rows.append((basket_item, unit_price, line_total))
        snapshot_items.append(
            SimpleNamespace(
                product_id=basket_item.product_id,
                variant_id=basket_item.variant_id,
                product_name=basket_item.product.name,
                product_sku=basket_item.product.sku,
                variant_name=variant.name,
                quantity=basket_item.quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    checkout_source = SimpleNamespace(
        delivery_address=basket.delivery_address,
        delivery_address_id=basket.delivery_address_id,
        recipient=basket.recipient,
        recipient_id=basket.recipient_id,
        items=snapshot_items,
        basket_subtotal=basket_subtotal,
        delivery_total=basket.delivery_total,
        grand_total=basket_subtotal + basket.delivery_total,
        currency=basket.currency,
        delivery_period_min=basket.delivery_period_min,
        delivery_period_max=basket.delivery_period_max,
        comment=None,
    )
    selected_delivery_service, selected_delivery_payload = await _build_selected_delivery_payload(checkout_source)
    discountable_subtotal = await discountable_subtotal_for_lines(
        session,
        ((item.product_id, line_total) for item, _, line_total in order_item_rows),
    )
    resolved_benefits = await _resolve_checkout_benefits(
        session,
        user=user,
        subtotal=basket_subtotal,
        discountable_subtotal=discountable_subtotal,
        currency=basket.currency,
        entered_code=entered_code,
    )
    grand_total = (quantize_money(resolved_benefits["total_after_discounts"]) or Decimal("0.00")) + basket.delivery_total
    checkout_snapshot = _build_checkout_snapshot(
        checkout_source,
        payment_method=payment_method,
        selected_delivery_service=selected_delivery_service,
        selected_delivery_payload=selected_delivery_payload,
        resolved_benefits=resolved_benefits,
    )
    delivery_string = _delivery_string(selected_delivery_service, normalize_address_for_cf(selected_delivery_payload.get("address")))

    order_code = await _generate_order_code(session)
    order_create = _build_order_create_data(
        user_id=user_id,
        delivery_address_id=basket.delivery_address_id,
        recipient_id=basket.recipient_id,
        order_code=order_code,
        items_count=len(order_item_rows),
        total_quantity=total_quantity,
        basket_subtotal=basket_subtotal,
        delivery_total=basket.delivery_total,
        grand_total=grand_total,
        currency=basket.currency,
        delivery_period_min=basket.delivery_period_min,
        delivery_period_max=basket.delivery_period_max,
        comment=None,
        delivery_string=delivery_string,
        selected_delivery_service=selected_delivery_service,
        selected_delivery_payload=selected_delivery_payload,
        checkout_snapshot=checkout_snapshot,
        payment_method=payment_method,
    )
    order = await create_order(session, order_create, commit=False)
    order_items = [_build_order_item_from_basket_row(user_id=user_id, order_id=order.id, row=row) for row in order_item_rows]
    session.add_all(order_items)
    await session.flush()
    await _persist_order_benefit_applications(session, order=order, user=user, resolved_benefits=resolved_benefits)
    for item, _, _ in order_item_rows: await record_purchase(session, user_id=user_id, product_id=item.product_id, quantity=item.quantity, commit=False)
    await ensure_order_has_amocrm_lead(session, order, user=user)
    await session.execute(delete(BasketItem).where(BasketItem.basket_id == basket.id))
    basket.delivery_address_id = None
    basket.recipient_id = None
    basket.delivery_total = Decimal("0.00")
    basket.currency = "RUB"
    basket.delivery_period_min = None
    basket.delivery_period_max = None
    await session.commit()

    created_order = await get_order_by_id(session, order.id, user_id=user_id)
    if created_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order")
    created_order_id = int(order.__dict__.get("id") or created_order.__dict__.get("id") or created_order.id)
    await sync_order_to_moysklad_safe(session, order=created_order, user=user)
    reloaded_order = await get_order_by_id(session, created_order_id, user_id=user_id)
    if reloaded_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order")
    return reloaded_order


async def get_order_for_user(session: AsyncSession, *, user_id: int, order_id: int) -> Order | None: return await get_order_by_id(session, order_id, user_id=user_id)
async def get_orders_history_for_user(session: AsyncSession, *, user_id: int, history_bucket: OrderHistoryBucket | None = None, status_code: OrderStatusCode | None = None, created_from: datetime | None = None, created_to: datetime | None = None, limit: int = 20, offset: int = 0) -> list[Order]: return await get_orders_for_user_crud(session, user_id, history_bucket=history_bucket, status_code=status_code, created_from=created_from, created_to=created_to, limit=limit, offset=offset)


async def _get_locked_variants_for_repeat(session: AsyncSession, variant_ids: list[int]) -> dict[int, Variant]:
    if not variant_ids:
        return {}

    stmt = (select(Variant).options(selectinload(Variant.product)).where(Variant.id.in_(variant_ids)).with_for_update())
    variants = list((await session.execute(stmt)).scalars().all())
    return {variant.id: variant for variant in variants}


async def repeat_order_as_draft_for_user(session: AsyncSession, *, user_id: int, order_id: int) -> OrderDraft | None:
    order = await get_order_by_id(session, order_id, user_id=user_id)
    if order is None: return None
    if get_order_history_bucket(order) != "completed": raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Повторить можно только завершенный заказ")
    if not order.items: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order is empty")

    variants_by_id = await _get_locked_variants_for_repeat(session, [item.variant_id for item in order.items])
    draft_items: list[OrderDraftItem] = []
    basket_subtotal = Decimal("0.00")
    total_quantity = 0

    for order_item in order.items:
        variant = variants_by_id.get(order_item.variant_id)
        if variant is None or variant.product is None: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order contains unavailable items")
        if variant.archived or variant.stock <= 0 or order_item.quantity > variant.stock: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order contains unavailable items")

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

    for draft_item in draft_items: draft_item.draft_id = draft.id
    session.add_all(draft_items)
    await session.flush()
    await session.commit()
    created_draft = await get_order_draft_by_id(session, draft.id, user_id=user_id)
    if created_draft is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load repeated order draft")
    return created_draft
