from config import MOY_SKLAD_ORDER_SYNC_ENABLED
from src.database.models import Order
from src.normalize import coerce_uuid, optional_str
from src.integrations.moysklad.client import get_moysklad_client
from .common import log
from .attributes import _href, _invoiceout_external_code, _is_intellectmoney_payment


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
        invoiceout = (await moysklad_client.get_invoiceout(order.moysklad_invoiceout_id) if order.moysklad_invoiceout_id else None)
        if invoiceout is None: invoiceout = await moysklad_client.find_invoiceout_by_external_code(_invoiceout_external_code(int(order_id)))
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
