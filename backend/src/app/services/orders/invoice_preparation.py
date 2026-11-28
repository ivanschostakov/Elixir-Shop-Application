from datetime import datetime, timedelta, timezone
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert

from src.database.models import IntegrationRun
from src.integrations.moysklad.settlement_checkout import order_settlement


class InvoicePreparationPending(RuntimeError):
    def __init__(self, delay):
        super().__init__("Waiting for the MoySklad invoice on the existing customer order")
        self.delay = delay


async def queue_invoice_sent(db, order):
    token = sha256(f"{order.id}:{order.payment_invoice_id}".encode()).hexdigest()
    await db.execute(insert(IntegrationRun).values(
        provider="moysklad", operation="mark_invoice_sent", target_type="order", target_id=str(order.id),
        input_json={"invoice_id": order.payment_invoice_id}, status="queued", attempts=0, max_attempts=8,
        counters_json={}, next_attempt_at=datetime.now(timezone.utc), idempotency_key="ms:invoice-sent:" + token,
    ).on_conflict_do_nothing(index_elements=[IntegrationRun.idempotency_key]))
    await db.commit()


async def mark_invoice_sent(db, order, expected):
    from sqlalchemy import select
    from src.database.models import Order
    from src.integrations.moysklad.order_sync import MOY_SKLAD_STATE_INVOICE_SENT, sync_moysklad_customerorder_state
    from src.integrations.moysklad.order_sync.common import MOY_SKLAD_STATE_NEW_ORDER

    await db.execute(select(Order.id).where(Order.id == order.id).with_for_update())
    await db.refresh(order)
    if (not order.payment_invoice_id or order.payment_invoice_id != expected.get("invoice_id")
            or order.is_canceled or order.is_paid or order.is_shipped or order.payment_status not in {"created", "pending"}):
        return {"skipped": "superseded"}
    changed = await sync_moysklad_customerorder_state(order, state_name=MOY_SKLAD_STATE_INVOICE_SENT,
        only_from=MOY_SKLAD_STATE_NEW_ORDER, strict=True)
    return {"order_id": order.id, "changed": changed}


async def queue_invoice_preparation(db, order):
    # Commit the job with the reserve acknowledgement; the worker recovers queued rows.
    await db.execute(insert(IntegrationRun).values(
        provider="moysklad", operation="prepare_robot_invoice", target_type="order", target_id=str(order.id),
        status="queued", attempts=0, max_attempts=10, counters_json={},
        next_attempt_at=datetime.now(timezone.utc) + timedelta(seconds=10),
        idempotency_key=f"ms:prepare-robot-invoice:{order.id}",
    ).on_conflict_do_nothing(index_elements=[IntegrationRun.idempotency_key]))


async def prepare_robot_invoice(db, order):
    from .settlement_payment import prepare_settlement_payment, settlement_lock
    from .payment_attempt import payment_backoff

    settlement = order_settlement(order)
    if not settlement or not settlement.get("counterparty_id"):
        return {"skipped": "not_robot_owned"}
    try:
        async with settlement_lock(settlement["counterparty_id"], payment=True):
            await db.refresh(order, attribute_names=["is_paid", "is_canceled", "payment_status",
                "checkout_snapshot", "moysklad_customerorder_id", "moysklad_invoiceout_id", "grand_total"])
            state = order_settlement(order) or {}
            if (order.is_paid or order.is_canceled or order.payment_status in {"refunded", "canceled"}
                    or not state):
                return {"skipped": "no_longer_waiting"}
            if state.get("status") == "confirmed":
                from .crm import sync_settlement_amount_to_crm
                await sync_settlement_amount_to_crm(db, order)
                return {"skipped": "invoice_already_confirmed"}
            hold = (order.checkout_snapshot or {}).get("stock_reservation") or {}
            if hold.get("status") != "exported" or not order.moysklad_customerorder_id:
                return {"skipped": "not_accepted"}
            async with payment_backoff(order.id, order.payment_method):
                await prepare_settlement_payment(db, order=order)
    except HTTPException as exc:
        if isinstance(exc.detail, dict) and exc.detail.get("code") == "settlement_pending":
            raise InvoicePreparationPending(int(exc.detail.get("retry_after_seconds") or 5)) from exc
        raise
    return {"order_id": order.id, "invoice_verified": True}
