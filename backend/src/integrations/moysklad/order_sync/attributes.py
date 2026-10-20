from typing import Any
from config import AMOCRM_BASE_URL, MOY_SKLAD_SALES_CHANNEL_HREF, MOY_SKLAD_IOS_SALES_CHANNEL_HREF, MOY_SKLAD_ANDROID_SALES_CHANNEL_HREF, MOY_SKLAD_TELEGRAM_SALES_CHANNEL_HREF
from src.database.models import Order
from src.normalize import extract_dict, lower_optional_str, optional_str
from src.integrations.moysklad.client import MoySkladClient
from src.integrations.moysklad.idempotency import build_customerorder_external_code
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
    # The MoySklad↔amoCRM widget treats false as a new unlinked order and creates
    # a second amoCRM lead. The app has already created and linked its lead, so
    # mark the order as widget-linked before it reaches MoySklad.
    values: dict[str, Any] = {
        "delivery_cost": optional_str(raw_values.get("delivery_cost")) or _delivery_cost_value(order),
        "created_by_widget": True,
    }

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
    }.get(platform) or MOY_SKLAD_SALES_CHANNEL_HREF
    sales_channel = _maybe_meta_row(channel_href, entity_type="saleschannel")

    return {"store": store, "state": state, "sales_channel": sales_channel}
