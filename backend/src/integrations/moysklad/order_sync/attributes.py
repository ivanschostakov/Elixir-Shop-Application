from typing import Any
from config import LOYALTY_COMPANY_PROMO_CODE
from config import AMOCRM_BASE_URL, MOY_SKLAD_SALES_CHANNEL_HREF, MOY_SKLAD_IOS_SALES_CHANNEL_HREF, MOY_SKLAD_ANDROID_SALES_CHANNEL_HREF, MOY_SKLAD_TELEGRAM_SALES_CHANNEL_HREF
from src.database.models import Order
from src.normalize import coerce_uuid, extract_dict, lower_optional_str, ms_referrer_code, optional_str
from src.integrations.moysklad.client import MoySkladClient
from src.integrations.moysklad.client.common import CUSTOMER_ORDER_ATTR_IDS
from src.integrations.moysklad.idempotency import build_customerorder_external_code
from src.integrations.moysklad.settlement_checkout import order_bonus_consent
from .common import MOY_SKLAD_DEFAULT_DELIVERY_METHOD_NAMES, MOY_SKLAD_PAYMENT_INTELLECT, MOY_SKLAD_PAYMENT_LATER, MOY_SKLAD_REQUIRED_STORE_NAME, MOY_SKLAD_STATE_NEW_ORDER
from .address import _delivery_cost_value


def _moysklad_order_data(order: Order) -> dict[str, Any]:
    return extract_dict(extract_dict(order.checkout_snapshot).get("moysklad"))


def _href(value: Any) -> str | None:
    normalized = optional_str(value)
    if not normalized or not normalized.startswith(("http://", "https://")): return None
    return normalized


def _order_payment_method_name(order: Order) -> str | None:
    return MOY_SKLAD_PAYMENT_LATER if lower_optional_str(order.payment_method) == "later" else MOY_SKLAD_PAYMENT_INTELLECT


_STANDARD_CHANNEL_IDS = {
    "ios": "52d06030-bbe7-11f1-0a80-016f000f8af5",
    "android": "58234296-bbe7-11f1-0a80-14c400102f30",
    "web": "2d64fbda-1887-11f1-0a80-07dd000e3c8f",
}


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


def customerorder_promo_code(snapshot: dict[str, Any]) -> str | None:
    benefits = extract_dict(snapshot.get("benefits"))
    # Only the server-side owner lookup populates this tuple. Draft text and
    # legacy CRM attributes are not proof, including when retrying an old order.
    code = ms_referrer_code(benefits.get("ms_order_promo"))
    buyer = coerce_uuid(benefits.get("ms_promo_buyer_id"))
    if not code or not buyer or "ms_referrer_id" not in benefits:
        return None
    if benefits["ms_referrer_id"] is None:
        company = ms_referrer_code(LOYALTY_COMPANY_PROMO_CODE)
        return company if company and company.casefold() == code.casefold() else None
    owner = coerce_uuid(benefits["ms_referrer_id"])
    return code if owner and owner != buyer else None


def _moysklad_attr_values(order: Order) -> dict[str, Any]:
    snapshot = extract_dict(order.checkout_snapshot)
    data = _moysklad_order_data(order)
    raw_values = extract_dict(data.get("attributes"))
    # The MoySklad↔amoCRM widget treats false as a new unlinked order and creates
    # a second amoCRM lead. The app has already created and linked its lead, so
    # mark the order as widget-linked before it reaches MoySklad.
    values: dict[str, Any] = {
        "delivery_cost": optional_str(raw_values.get("delivery_cost")) or _delivery_cost_value(order),
        "created_by_widget": True,
    }
    settlement = snapshot.get("settlement_payment") or {}
    automatic = settlement.get("mode") == "automatic"
    if "balance_consent" in CUSTOMER_ORDER_ATTR_IDS and not automatic:
        values["balance_consent"] = order_bonus_consent(order)
    if "balance_amount_kopecks" in CUSTOMER_ORDER_ATTR_IDS and not automatic:
        from decimal import Decimal
        settlement = (order.checkout_snapshot or {}).get("settlement_payment") or {}
        values["balance_amount_kopecks"] = int(Decimal(str(settlement.get("requested_balance_rubles", "0"))) * 100) if order_bonus_consent(order) else 0

    promo_code = customerorder_promo_code(snapshot)
    if promo_code: values["promo_code"] = promo_code
    deal_link = _amocrm_lead_link(order) or optional_str(raw_values.get("deal_link")) or optional_str(data.get("deal_link"))
    if deal_link: values["deal_link"] = deal_link
    for key in ("client_waybill_link", "tracking_number", "site_order_link", "delivery_tracking"):
        value = optional_str(raw_values.get(key)) or optional_str(data.get(key))
        if value: values[key] = value
    return values


def _amocrm_lead_link(order: Order) -> str | None:
    lead_id = optional_str(order.__dict__.get("amocrm_lead_id"))
    base_url = optional_str(AMOCRM_BASE_URL)
    if not lead_id or not base_url: return None
    normalized_domain = base_url.replace("https://", "").replace("http://", "").strip("/")
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

    platform = extract_dict(order.checkout_snapshot).get("client_platform")
    channel_href = {
        "ios": MOY_SKLAD_IOS_SALES_CHANNEL_HREF,
        "android": MOY_SKLAD_ANDROID_SALES_CHANNEL_HREF,
        "web": MOY_SKLAD_TELEGRAM_SALES_CHANNEL_HREF,
    }.get(platform)
    if not channel_href and extract_dict(order.checkout_snapshot).get("order_export_version") and platform in _STANDARD_CHANNEL_IDS:
        channel_href = moysklad_client.entity_href("saleschannel", _STANDARD_CHANNEL_IDS[platform])
    channel_href = channel_href or MOY_SKLAD_SALES_CHANNEL_HREF
    sales_channel = _maybe_meta_row(channel_href, entity_type="saleschannel")

    return {"store": store, "state": state, "sales_channel": sales_channel}
