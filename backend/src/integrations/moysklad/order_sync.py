from decimal import Decimal, ROUND_HALF_UP
import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import AMOCRM_BASE_DOMAIN, MOY_SKLAD_ORDER_SYNC_ENABLED, MOY_SKLAD_ORGANIZATION_ID, MOY_SKLAD_SALES_CHANNEL_HREF
from src.database.models import Order, Product, User, Variant
from src.integrations.delivery.schemas import COUNTRY_NAMES
from src.normalize import coerce_uuid, extract_dict, lower_optional_str, optional_str

from .client import MoySkladClient, get_moysklad_client
from .idempotency import (
    build_counterparty_external_code,
    build_customerorder_external_code,
    build_sync_id,
)
from .rows import synthetic_variant_id
from .schemas import MoySkladOrderSyncResult

log = logging.getLogger(__name__)
MOY_SKLAD_REQUIRED_STORE_NAME = "Основной склад"
MOY_SKLAD_STATE_NEW_ORDER = "Новый заказ"
MOY_SKLAD_STATE_INVOICE_SENT = "Счет отправлен"
MOY_SKLAD_STATE_INVOICE_PAID = "Счет оплачен"
MOY_SKLAD_INVOICEOUT_STATE_PAID = "Оплачен"
MOY_SKLAD_PAYMENT_LATER = "СБП через менеджера"
MOY_SKLAD_PAYMENT_INTELLECT = "IntellectMoney"
MOY_SKLAD_DEFAULT_DELIVERY_METHOD_NAMES = {"CDEK": "СДЭК", "YANDEX": "Яндекс.Доставка"}
_STREET_HINT_RE = re.compile(r"\b(ул\.?|улиц|пр-?кт|просп|пер\.?|переул|бул\.?|бульв|наб\.?|набереж|ш\.?|шоссе|проезд|пр-д|пл\.?|площадь|аллея|тупик)\b", re.IGNORECASE)
_HOUSE_RE = re.compile(r"\b(?:д\.?|дом)\s*([0-9A-Za-zА-Яа-я/-]+(?:\s*(?:к(?:орп)?\.?|стр\.?|с)\s*[0-9A-Za-zА-Яа-я/-]+)?)", re.IGNORECASE)
_APARTMENT_RE = re.compile(r"\b(?:кв\.?|квартира|ап\.?|apartment|офис|оф\.?)\s*([0-9A-Za-zА-Яа-я/-]+)", re.IGNORECASE)
_REGION_HINT_RE = re.compile(r"\b(обл\.?|область|край|респ\.?|республика|автономный округ|ао)\b", re.IGNORECASE)
_BUILDING_HINT_RE = re.compile(r"\b(корп\.?|корпус|стр\.?|строение|лит\.?)\b", re.IGNORECASE)


def _full_name(user: User, order: Order) -> str:
    recipient = order.recipient
    parts = [
        optional_str(recipient.name) if recipient is not None else None,
        optional_str(recipient.surname) if recipient is not None else None,
    ]
    full_name = " ".join(part for part in parts if part)
    if full_name: return full_name

    fallback_parts = [optional_str(user.name), optional_str(user.surname)]
    fallback_name = " ".join(part for part in fallback_parts if part)
    if fallback_name: return fallback_name

    email_fallback = optional_str(user.email)
    if email_fallback: return email_fallback
    return f"User {user.__dict__.get('id') or 'unknown'}"


def _counterparty_email(user: User, order: Order) -> str | None:
    recipient = order.recipient
    if recipient is not None:
        recipient_email = optional_str(recipient.email)
        if recipient_email: return recipient_email

    return optional_str(user.email)


def _counterparty_phone(user: User, order: Order) -> str | None:
    recipient = order.recipient
    if recipient is not None:
        recipient_phone = optional_str(recipient.phone)
        if recipient_phone: return recipient_phone

    return optional_str(user.phone_number)


def _counterparty_address(order: Order) -> str | None:
    if order.delivery_address is not None:
        address = optional_str(order.delivery_address.full_address)
        if address: return address

    return optional_str(order.delivery_string)


def _configured_organization_id() -> UUID | None:
    configured_id = coerce_uuid(MOY_SKLAD_ORGANIZATION_ID)
    if configured_id is None and optional_str(MOY_SKLAD_ORGANIZATION_ID): log.warning("MOY_SKLAD_ORGANIZATION_ID is not a valid UUID: %s", MOY_SKLAD_ORGANIZATION_ID)
    return configured_id


async def _load_assortment_refs(session: AsyncSession, *, variant_ids: list[int]) -> dict[int, tuple[str, UUID]]:
    if not variant_ids: return {}
    stmt = select(Variant.id, Variant.system_id, Product.system_id) .join(Product, Product.id == Variant.product_id) .where(Variant.id.in_(variant_ids))

    rows = (await session.execute(stmt)).all()
    refs: dict[int, tuple[str, UUID]] = {}
    for variant_id, variant_system_id, product_system_id in rows:
        if variant_system_id is not None and product_system_id is not None and variant_system_id == synthetic_variant_id(product_system_id):
            refs[int(variant_id)] = ("product", product_system_id)
            continue
        if variant_system_id is not None:
            refs[int(variant_id)] = ("variant", variant_system_id)
            continue

        if product_system_id is not None: refs[int(variant_id)] = ("product", product_system_id)
    return refs


def _build_customerorder_positions(*, moysklad_client: MoySkladClient, assortment_refs: dict[int, tuple[str, UUID]], order: Order) -> tuple[list[dict[str, Any]], list[int]]:
    positions: list[dict[str, Any]] = []
    missing_variant_ids: list[int] = []
    discount_percent = _order_positions_discount_percent(order)

    for item in order.items:
        assortment_ref = assortment_refs.get(int(item.variant_id))
        if assortment_ref is None:
            missing_variant_ids.append(int(item.variant_id))
            continue

        entity_type, entity_id = assortment_ref
        positions.append(moysklad_client.build_customerorder_position(
            assortment_entity_type=entity_type,
            assortment_id=entity_id,
            quantity=item.quantity,
            unit_price=Decimal(item.unit_price),
            discount=discount_percent,
        ))

    return positions, missing_variant_ids


def _build_order_description(order: Order) -> str:
    comment = optional_str(order.comment)
    if comment: return f"{order.order_code}. {comment}"
    return order.order_code


def _delivery_cost_value(order: Order) -> str:
    return f"{Decimal(order.delivery_total):.2f}"


def _decimal_or_zero(value: Any) -> Decimal:
    try: return Decimal(str(value))
    except Exception: return Decimal("0.00")


def _order_positions_discount_percent(order: Order) -> Decimal:
    benefits = extract_dict(extract_dict(order.checkout_snapshot).get("benefits"))
    subtotal = _decimal_or_zero(benefits.get("basket_subtotal"))
    discount_amount = _decimal_or_zero(benefits.get("stacked_discount_amount"))
    if discount_amount <= Decimal("0.00"):
        total_after = _decimal_or_zero(benefits.get("total_after_discounts"))
        if total_after > Decimal("0.00") and total_after < subtotal: discount_amount = subtotal - total_after
    if discount_amount <= Decimal("0.00"):
        options = benefits.get("stacked_discount_options")
        if isinstance(options, list): discount_amount = sum((_decimal_or_zero(extract_dict(option).get("discount_amount")) for option in options), Decimal("0.00"))
    if subtotal <= Decimal("0.00") or discount_amount <= Decimal("0.00"): return Decimal("0.00")
    return max(Decimal("0.00"), min(Decimal("100.00"), ((discount_amount * Decimal("100.00")) / subtotal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))


def _shipment_address(order: Order) -> str | None:
    if order.delivery_address is not None:
        full = optional_str(order.delivery_address.full_address)
        if full: return full
    return optional_str(order.delivery_string)


def _address_segments(full: str) -> list[str]:
    return [segment.strip() for segment in full.split(",") if optional_str(segment)]


def _extract_street(full: str) -> str | None:
    for segment in _address_segments(full):
        if _STREET_HINT_RE.search(segment):
            return segment
    return None


def _extract_house(full: str, *, street: str | None = None) -> str | None:
    explicit = _HOUSE_RE.search(full)
    if explicit:
        return optional_str(explicit.group(1))

    segments = _address_segments(full)
    if not segments:
        return None
    if street is None:
        street = _extract_street(full)
    if not street:
        return None

    for index, segment in enumerate(segments):
        if segment != street:
            continue
        if index + 1 >= len(segments):
            return None
        next_segment = segments[index + 1]
        if not re.fullmatch(r"[0-9A-Za-zА-Яа-я/-]+", next_segment):
            return None
        if index + 2 < len(segments) and _BUILDING_HINT_RE.search(segments[index + 2]):
            return f"{next_segment}, {segments[index + 2]}"
        return next_segment
    return None


def _extract_apartment(full: str) -> str | None:
    apartment = _APARTMENT_RE.search(full)
    if apartment:
        return optional_str(apartment.group(1))
    return None


def _extract_region(full: str) -> str | None:
    for segment in _address_segments(full):
        if _REGION_HINT_RE.search(segment):
            return segment
    return None


def _country_name_from_payload(country_name: Any, country_code: Any) -> str | None:
    normalized_name = optional_str(country_name)
    if normalized_name:
        return normalized_name
    normalized_code = optional_str(country_code)
    if not normalized_code:
        return None
    return COUNTRY_NAMES.get(normalized_code.upper())  # type: ignore[arg-type]


async def _shipment_address_full(order: Order, *, moysklad_client: MoySkladClient) -> dict[str, Any] | None:
    payload = extract_dict(order.selected_delivery_payload)
    address = extract_dict(payload.get("address"))
    full = optional_str(address.get("full_address")) or optional_str(address.get("formatted")) or optional_str(address.get("address")) or _shipment_address(order)
    if not full: return None

    result: dict[str, Any] = {}
    city = optional_str(address.get("city")) or (optional_str(order.delivery_address.city) if order.delivery_address is not None else None)
    postal = optional_str(address.get("postal_code")) or (optional_str(order.delivery_address.postal_code) if order.delivery_address is not None else None)
    details = optional_str(address.get("details")) or (optional_str(order.delivery_address.details) if order.delivery_address is not None else None)
    street = optional_str(address.get("street")) or _extract_street(full)
    house = optional_str(address.get("house")) or _extract_house(full, street=street)
    apartment = optional_str(address.get("apartment")) or _extract_apartment(full)
    region_name = optional_str(address.get("region")) or _extract_region(full)
    country_code = optional_str(address.get("country_code")) or (optional_str(order.delivery_address.country_code) if order.delivery_address is not None else None)
    country_name = _country_name_from_payload(address.get("country"), country_code)
    country_row = await moysklad_client.find_country_by_name_or_code(country_code or "", country_name or "")

    if city: result["city"] = city
    if postal: result["postalCode"] = postal
    if details: result["comment"] = details
    if street: result["street"] = street
    if house: result["house"] = house
    if apartment: result["apartment"] = apartment
    if country_row and isinstance(country_row.get("meta"), dict):
        result["country"] = {"meta": country_row["meta"]}
    if region_name:
        country_id = coerce_uuid(country_row.get("id")) if country_row is not None else None
        region_row = await moysklad_client.find_region_by_name(region_name, country_id=country_id)
        if region_row and isinstance(region_row.get("meta"), dict):
            result["region"] = {"meta": region_row["meta"]}
    # MoySklad renders shipmentAddressFull as a combined human string.
    # Sending the full address in addInfo alongside structured fields duplicates the address in UI.
    has_structured_location = any(result.get(field_name) for field_name in ("city", "postalCode", "street", "house", "apartment"))
    if not has_structured_location:
        result["addInfo"] = full
    return result


def _moysklad_order_data(order: Order) -> dict[str, Any]:
    return extract_dict(extract_dict(order.checkout_snapshot).get("moysklad"))


def _href(value: Any) -> str | None:
    normalized = optional_str(value)
    if not normalized or not normalized.startswith(("http://", "https://")): return None
    return normalized


def _order_payment_method_name(order: Order) -> str | None:
    return MOY_SKLAD_PAYMENT_LATER if lower_optional_str(order.payment_method) == "later" else MOY_SKLAD_PAYMENT_INTELLECT


def _is_intellectmoney_payment(order: Order) -> bool:
    payment_method = lower_optional_str(order.payment_method)
    payment_provider = lower_optional_str(order.payment_provider)
    return payment_method == "sbp" or payment_provider == "intellectmoney"


def _invoiceout_external_code(order_id: int) -> str:
    return f"{build_customerorder_external_code(order_id=order_id)}:invoiceout"


def _invoiceout_name(order: Order) -> str:
    order_code = optional_str(order.__dict__.get("order_code")) or optional_str(order.__dict__.get("id")) or "order"
    return f"Счет по заказу {order_code}"


def _order_state_name(order: Order) -> str:
    return MOY_SKLAD_STATE_NEW_ORDER


def _order_delivery_method_name(order: Order) -> str | None:
    selected_delivery_service = optional_str(order.selected_delivery_service)
    if not selected_delivery_service: return None
    return MOY_SKLAD_DEFAULT_DELIVERY_METHOD_NAMES.get(selected_delivery_service.upper())


async def _moysklad_custom_attr_refs(moysklad_client: MoySkladClient, order: Order) -> dict[str, str]:
    refs: dict[str, str] = {}
    payment_method_name = _order_payment_method_name(order)
    if payment_method_name:
        payment_method = await moysklad_client.find_customerorder_customentity_value("payment_method", payment_method_name)
        payment_method_href = _href((payment_method or {}).get("meta", {}).get("href"))
        if payment_method_href: refs["payment_method"] = payment_method_href

    delivery_method_name = _order_delivery_method_name(order)
    if delivery_method_name:
        delivery_method = await moysklad_client.find_customerorder_customentity_value("delivery_method", delivery_method_name)
        delivery_method_href = _href((delivery_method or {}).get("meta", {}).get("href"))
        if delivery_method_href: refs["delivery_method"] = delivery_method_href
    return refs


def _moysklad_attr_values(order: Order) -> dict[str, Any]:
    snapshot = extract_dict(order.checkout_snapshot)
    benefits = extract_dict(snapshot.get("benefits"))
    data = _moysklad_order_data(order)
    raw_values = extract_dict(data.get("attributes"))
    values: dict[str, Any] = {"delivery_cost": optional_str(raw_values.get("delivery_cost")) or _delivery_cost_value(order), "created_by_widget": False}

    promo_code = optional_str(raw_values.get("promo_code")) or optional_str(data.get("promo_code")) or optional_str(benefits.get("entered_code"))
    if promo_code: values["promo_code"] = promo_code
    deal_link = _amocrm_lead_link(order) or optional_str(raw_values.get("deal_link")) or optional_str(data.get("deal_link"))
    if deal_link: values["deal_link"] = deal_link
    for key in ("client_waybill_link", "tracking_number", "site_order_link", "delivery_tracking"):
        value = optional_str(raw_values.get(key)) or optional_str(data.get(key))
        if value: values[key] = value
    return values


def _amocrm_lead_link(order: Order) -> str | None:
    lead_id = optional_str(order.__dict__.get("amocrm_lead_id"))
    domain = optional_str(AMOCRM_BASE_DOMAIN)
    if not lead_id or not domain: return None
    normalized_domain = domain.replace("https://", "").replace("http://", "").strip("/")
    if not normalized_domain: return None
    return f"https://{normalized_domain}/leads/detail/{lead_id}"


def _maybe_meta_row(value: Any, *, entity_type: str) -> dict[str, Any] | None:
    if isinstance(value, dict) and isinstance(value.get("meta"), dict): return {"meta": value["meta"]}
    if isinstance(value, dict):
        href = optional_str(value.get("href"))
        if href: return {"meta": {"href": href, "type": optional_str(value.get("type")) or entity_type, "mediaType": "application/json"}}
    href = optional_str(value)
    if not href: return None
    return {"meta": {"href": href, "type": entity_type, "mediaType": "application/json"}}


async def _resolve_customerorder_refs(moysklad_client: MoySkladClient, order: Order) -> dict[str, dict[str, Any] | None]:
    store = _maybe_meta_row(await moysklad_client.find_store_by_name(MOY_SKLAD_REQUIRED_STORE_NAME), entity_type="store")
    state = _maybe_meta_row(await moysklad_client.find_customerorder_state_by_name(_order_state_name(order)), entity_type="state")

    sales_channel = _maybe_meta_row(MOY_SKLAD_SALES_CHANNEL_HREF, entity_type="saleschannel")

    return {"store": store, "state": state, "sales_channel": sales_channel}


async def sync_moysklad_customerorder_state(order: Order, *, state_name: str) -> bool:
    normalized_state_name = optional_str(state_name)
    if not MOY_SKLAD_ORDER_SYNC_ENABLED or not normalized_state_name: return False
    if order.moysklad_customerorder_id is None: return False
    moysklad_client = get_moysklad_client()
    if not moysklad_client.is_configured(): return False
    try:
        state = await moysklad_client.find_customerorder_state_by_name(normalized_state_name)
        if state is None:
            log.warning("Skipping MoySklad customerorder state sync because state not found state_name=%s order_id=%s", normalized_state_name, order.id)
            return False
        current_order = await moysklad_client.get_customer_order(order.moysklad_customerorder_id)
        current_state = current_order.get("state") if isinstance(current_order, dict) else None
        current_meta = current_state.get("meta") if isinstance(current_state, dict) else None
        current_state_href = _href(current_meta.get("href")) if isinstance(current_meta, dict) else None
        target_state_href = _href((state.get("meta") or {}).get("href"))
        if current_state_href and target_state_href and current_state_href == target_state_href: return False
        await moysklad_client.update_customer_order_state(order.moysklad_customerorder_id, state)
        return True
    except Exception:
        log.exception("MoySklad customerorder state sync failed order_id=%s moysklad_customerorder_id=%s state_name=%s", order.id, order.moysklad_customerorder_id, normalized_state_name)
        return False


async def sync_moysklad_invoiceout_state(order: Order, *, state_name: str) -> bool:
    normalized_state_name = optional_str(state_name)
    if not MOY_SKLAD_ORDER_SYNC_ENABLED or not normalized_state_name: return False
    if not _is_intellectmoney_payment(order): return False
    order_id = order.__dict__.get("id")
    if order_id is None: return False
    moysklad_client = get_moysklad_client()
    if not moysklad_client.is_configured(): return False
    try:
        invoiceout = await moysklad_client.find_invoiceout_by_external_code(_invoiceout_external_code(int(order_id)))
        if invoiceout is None:
            log.warning("Skipping MoySklad invoiceout state sync because invoiceout not found order_id=%s state_name=%s", order_id, normalized_state_name)
            return False
        invoiceout_id = coerce_uuid(invoiceout.get("id"))
        if invoiceout_id is None:
            log.warning("Skipping MoySklad invoiceout state sync because invoiceout id is invalid order_id=%s state_name=%s", order_id, normalized_state_name)
            return False
        state = await moysklad_client.find_invoiceout_state_by_name(normalized_state_name)
        if state is None:
            log.warning("Skipping MoySklad invoiceout state sync because state not found state_name=%s order_id=%s", normalized_state_name, order_id)
            return False
        current_state = invoiceout.get("state") if isinstance(invoiceout, dict) else None
        current_meta = current_state.get("meta") if isinstance(current_state, dict) else None
        current_state_href = _href(current_meta.get("href")) if isinstance(current_meta, dict) else None
        target_state_href = _href((state.get("meta") or {}).get("href"))
        if current_state_href and target_state_href and current_state_href == target_state_href: return False
        await moysklad_client.update_invoiceout_state(invoiceout_id, state)
        return True
    except Exception:
        log.exception("MoySklad invoiceout state sync failed order_id=%s state_name=%s", order_id, normalized_state_name)
        return False


async def sync_order_to_moysklad(session: AsyncSession, *, order: Order, user: User) -> MoySkladOrderSyncResult:
    if not MOY_SKLAD_ORDER_SYNC_ENABLED: return MoySkladOrderSyncResult(enabled=False, skipped_reason="disabled")

    moysklad_client = get_moysklad_client()
    if not moysklad_client.is_configured(): return MoySkladOrderSyncResult(enabled=True, skipped_reason="client_not_configured")
    if not order.items: return MoySkladOrderSyncResult(enabled=True, skipped_reason="empty_order")

    organization_id = _configured_organization_id()
    if organization_id is None: return MoySkladOrderSyncResult(enabled=True, skipped_reason="organization_not_configured")

    user_id = int(user.__dict__.get("id") or user.id)
    counterparty_external_code = build_counterparty_external_code(user_id=user_id)
    counterparty_sync_id = build_sync_id(scope="counterparty", key=counterparty_external_code)
    counterparty_result = await moysklad_client.resolve_or_sync_counterparty(
        existing_counterparty_id=user.moysklad_counterparty_id,
        external_code=counterparty_external_code,
        sync_id=counterparty_sync_id,
        name=_full_name(user, order),
        email=_counterparty_email(user, order),
        phone=_counterparty_phone(user, order),
        actual_address=_counterparty_address(order),
    )

    if user.moysklad_counterparty_id != counterparty_result.counterparty_id:
        user.moysklad_counterparty_id = counterparty_result.counterparty_id
        await session.flush()
        await session.commit()

    variant_ids = [int(item.variant_id) for item in order.items]
    assortment_refs = await _load_assortment_refs(session, variant_ids=variant_ids)
    positions, missing_variant_ids = _build_customerorder_positions(
        moysklad_client=moysklad_client,
        assortment_refs=assortment_refs,
        order=order,
    )

    if missing_variant_ids:
        unique_missing = sorted(set(missing_variant_ids))
        log.warning("Skipping MoySklad order sync because assortment refs are missing for variants=%s order_id=%s", unique_missing, order.id)
        return MoySkladOrderSyncResult(
            enabled=True,
            skipped_reason="missing_assortment_refs",
            counterparty=counterparty_result,
        )

    if not positions: return MoySkladOrderSyncResult(
        enabled=True,
        skipped_reason="empty_positions",
        counterparty=counterparty_result,
    )

    customerorder_external_code = build_customerorder_external_code(order_id=order.id)
    customerorder_sync_id = build_sync_id(scope="customerorder", key=customerorder_external_code)
    refs = await _resolve_customerorder_refs(moysklad_client, order)
    if refs["store"] is None: return MoySkladOrderSyncResult(enabled=True, skipped_reason="store_not_configured", counterparty=counterparty_result)
    if refs["state"] is None: return MoySkladOrderSyncResult(enabled=True, skipped_reason="state_not_configured", counterparty=counterparty_result)
    if refs["sales_channel"] is None: return MoySkladOrderSyncResult(enabled=True, skipped_reason="sales_channel_not_configured", counterparty=counterparty_result)
    attributes = moysklad_client.build_customerorder_attributes(values=_moysklad_attr_values(order), custom_refs=await _moysklad_custom_attr_refs(moysklad_client, order))
    customerorder_result = await moysklad_client.resolve_or_sync_customerorder(
        existing_customerorder_id=order.moysklad_customerorder_id,
        external_code=customerorder_external_code,
        sync_id=customerorder_sync_id,
        organization_id=organization_id,
        counterparty_id=counterparty_result.counterparty_id,
        positions=positions,
        moment=order.created_at,
        description=_build_order_description(order),
        shipment_address=_shipment_address(order),
        shipment_address_full=await _shipment_address_full(order, moysklad_client=moysklad_client),
        attributes=attributes,
        store=refs["store"],
        state=refs["state"],
        sales_channel=refs["sales_channel"],
    )
    invoiceout_result = None
    if _is_intellectmoney_payment(order):
        order_id = int(order.__dict__.get("id") or order.id)
        invoiceout_external_code = _invoiceout_external_code(order_id)
        invoiceout_sync_id = build_sync_id(scope="invoiceout", key=invoiceout_external_code)
        invoiceout_result = await moysklad_client.resolve_or_sync_invoiceout(
            external_code=invoiceout_external_code,
            sync_id=invoiceout_sync_id,
            name=_invoiceout_name(order),
            organization_id=organization_id,
            counterparty_id=counterparty_result.counterparty_id,
            positions=positions,
            customerorder_id=customerorder_result.customerorder_id,
            moment=order.created_at,
            description=_build_order_description(order),
            store=refs["store"],
            sales_channel=refs["sales_channel"],
        )

    needs_commit = False
    if order.moysklad_customerorder_id != customerorder_result.customerorder_id:
        order.moysklad_customerorder_id = customerorder_result.customerorder_id
        needs_commit = True
    if invoiceout_result is not None and order.moysklad_invoiceout_id != invoiceout_result.invoiceout_id:
        order.moysklad_invoiceout_id = invoiceout_result.invoiceout_id
        needs_commit = True
    if needs_commit:
        await session.flush()
        await session.commit()

    return MoySkladOrderSyncResult(
        enabled=True,
        counterparty=counterparty_result,
        customerorder=customerorder_result,
        invoiceout=invoiceout_result,
    )


async def sync_order_to_moysklad_safe(session: AsyncSession, *, order: Order, user: User) -> MoySkladOrderSyncResult:
    try: return await sync_order_to_moysklad(session, order=order, user=user)
    except Exception:
        order_id = order.__dict__.get("id")
        user_id = user.__dict__.get("id")
        requires_rollback = not session.is_active
        if requires_rollback:
            try: await session.rollback()
            except Exception: log.exception("MoySklad rollback after sync failure also failed order_id=%s user_id=%s", order_id, user_id)
        log.exception("MoySklad order sync failed order_id=%s user_id=%s rollback=%s", order_id, user_id, requires_rollback)
        return MoySkladOrderSyncResult(enabled=MOY_SKLAD_ORDER_SYNC_ENABLED, skipped_reason="sync_error")
