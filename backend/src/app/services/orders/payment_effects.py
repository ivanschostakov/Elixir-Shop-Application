from hashlib import sha256
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from src.database.models import IntegrationRun

async def queue_payment_effects(db, order):
    if order.payment_status not in {"paid", "refunded", "canceled", "error", "hold", "partial"}:
        return None
    key = "payment-effects:" + sha256(f"{order.id}:{order.payment_invoice_id}:{order.payment_status}".encode()).hexdigest()
    await db.execute(insert(IntegrationRun).values(provider="app", operation="payment_effects",
        target_type="order", target_id=str(order.id), status="queued", attempts=0, max_attempts=12,
        next_attempt_at=datetime.now(timezone.utc), idempotency_key=key,
        input_json={"invoice_id": order.payment_invoice_id, "payment_status": order.payment_status}, counters_json={}
    ).on_conflict_do_nothing())
    return (await db.execute(select(IntegrationRun.id).where(IntegrationRun.idempotency_key == key))).scalar_one()

async def try_payment_effects(run_id):
    if run_id is None: return
    from src.app.services.admin.jobs import execute_integration_run
    try:
        await execute_integration_run(run_id)
    except Exception:
        # The committed run is recovered by the existing durable job worker.
        import logging
        logging.getLogger(__name__).exception("Payment effects deferred run_id=%s", run_id)

async def apply_payment_effects(db, order, expected):
    if order.payment_invoice_id != expected.get("invoice_id") or order.payment_status != expected.get("payment_status"):
        return {"skipped": "superseded"}
    from .crm import _move_lead_to_payment_result_status
    from src.integrations.moysklad.order_sync import sync_moysklad_customerorder_state, sync_moysklad_invoiceout_state, MOY_SKLAD_STATE_INVOICE_PAID, MOY_SKLAD_INVOICEOUT_STATE_PAID
    await _move_lead_to_payment_result_status(db, order, payment_status=order.payment_status)
    if order.payment_status == "paid":
        await sync_moysklad_customerorder_state(order, state_name=MOY_SKLAD_STATE_INVOICE_PAID, strict=True)
        await sync_moysklad_invoiceout_state(order, state_name=MOY_SKLAD_INVOICEOUT_STATE_PAID, strict=True)
    return {"order_id": order.id, "payment_status": order.payment_status}
