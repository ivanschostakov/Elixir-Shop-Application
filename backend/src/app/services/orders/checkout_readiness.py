"""Customer-visible checkout status, separate from the CRM pipeline stage."""

import uuid

import config
from src.database.models.orders.history import get_order_status_code
from src.integrations.moysklad.settlement_checkout import order_settlement


def checkout_preparing(order) -> bool:
    snapshot = getattr(order, "checkout_snapshot", None) or {}
    if not config.MOY_SKLAD_ORDER_SYNC_ENABLED or snapshot.get("order_export_version") != 1:
        return False
    if order.is_paid or order.is_canceled or order.is_shipped or get_order_status_code(order) not in {"created", "invoice_sent"}:
        return False
    if not order.amocrm_lead_id or not order.moysklad_customerorder_id or not order.moysklad_invoiceout_id:
        return True
    settlement = order_settlement(order)
    if settlement and settlement.get("status") != "confirmed":
        return True
    if order.payment_method == "later":
        return order.payment_provider != "manager" or order.payment_status != "pending"
    return not order.payment_invoice_id or snapshot.get("sbp_ready_invoice_id") != str(order.payment_invoice_id)


def customer_order_status(order):
    return "preparing" if checkout_preparing(order) else get_order_status_code(order)


async def record_created_when_ready(db, order, *, verified_checkout=False):
    from src.app.services.customer_intelligence import record_customer_event_safe
    if order.is_canceled or order.payment_status in {"error", "refunded", "canceled"} or (
        not verified_checkout and checkout_preparing(order)
    ):
        return
    await record_customer_event_safe(
        db, user_id=order.user_id, event_name="order_created",
        event_id=uuid.uuid5(uuid.NAMESPACE_URL, f"elixir-shop:user:{order.user_id}:order:{order.id}:created"),
        entity_type="order", entity_id=order.id,
        properties={"order_code": order.order_code, "grand_total": str(order.grand_total), "currency": order.currency},
        commit=True,
    )
