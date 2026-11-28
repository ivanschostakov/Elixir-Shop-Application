"""The order commit owns the checkout intent. Redis only wakes the worker."""
import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

import config
from src.database.crud import get_order_by_id
from src.database.models import IntegrationRun
from src.integrations.moysklad.order_sync import sync_order_to_moysklad
from src.integrations.moysklad.settlement_checkout import order_settlement
from . import payments
from .crm import ensure_order_has_amocrm_lead
from .invoice_preparation import InvoicePreparationPending
from .checkout_lifecycle import OPERATION, WINDOW, public_issue
from src.database.models.orders.history import STATUS_LABELS_BY_CODE

log = logging.getLogger(__name__)


def _key(order_id):
    return f"app:complete-checkout:{order_id}"


def _approved_terms(order):
    settlement = order_settlement(order)
    if not settlement:
        return {"currency": order.currency, "total": format(order.grand_total, ".2f")}
    # The invoice may legitimately change cash due, but not the original consent.
    return {"currency": order.currency, "settlement": {key: settlement.get(key) for key in (
        "counterparty_id", "mode", "gross_rubles", "maximum_balance_rubles", "requested_balance_rubles")}}


async def stage_checkout(db, order, request, *, prepare_order=False):
    # Do not commit here: stock, basket consumption and this outbox row are atomic.
    ip = next((ip for key in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for", "forwarded")
               if (ip := payments._ipv4_from_value(request.headers.get(key)))), None)
    ip = ip or payments._ipv4_from_value(request.client.host if request.client else None)
    now = datetime.now(timezone.utc)
    run_id = await db.scalar(insert(IntegrationRun).values(
        provider="app", operation=OPERATION, target_type="order", target_id=str(order.id),
        idempotency_key=_key(order.id), input_json={"method": order.payment_method, "ip": ip,
                                                   "prepare_order": prepare_order, "terms": _approved_terms(order)},
        status="queued", attempts=0, max_attempts=720, counters_json={}, started_at=now, next_attempt_at=now,
    ).on_conflict_do_nothing(index_elements=[IntegrationRun.idempotency_key]).returning(IntegrationRun.id))
    if run_id is not None and order.status in STATUS_LABELS_BY_CODE["created"]:
        order.status = STATUS_LABELS_BY_CODE["processing"][0]
    if run_id is not None and prepare_order:
        hold = (order.checkout_snapshot or {}).get("stock_reservation", {})
        if hold.get("status") == "held":
            order.checkout_snapshot = {**order.checkout_snapshot, "stock_reservation": {
                **hold, "expires_at": (now + WINDOW).isoformat()}}
    return run_id


async def notify_worker(run_id):
    from src.app.services.admin.jobs import enqueue_integration_run
    try:
        await asyncio.wait_for(enqueue_integration_run(run_id), timeout=0.25)
    except Exception:
        log.warning("Checkout run %s left for periodic recovery", run_id)


async def commit_created_order(db, order, checkout_request):
    run_id = (await stage_checkout(db, order, checkout_request, prepare_order=True)
              if checkout_request is not None else None)
    await db.commit()
    if run_id is not None:
        await notify_worker(run_id)


async def claim_payment(db, order):
    # Keep the one-shot decision on the intent as well as on the order.
    # Later status updates or an operator retry cannot reset this fence.
    run = await db.scalar(select(IntegrationRun).where(
        IntegrationRun.idempotency_key == _key(order.id)).with_for_update().execution_options(populate_existing=True))
    if run is None or run.status != "running" or run.input_json.get("payment_submitted"):
        raise HTTPException(409, "Payment submission requires reconciliation")
    if "terms" in run.input_json and run.input_json["terms"] != _approved_terms(order):
        raise HTTPException(409, "Checkout terms have changed")
    run.input_json = {**run.input_json, "payment_submitted": True}


async def bind_checkout_invoice(db, order, invoice_id):
    run = await db.scalar(select(IntegrationRun).where(IntegrationRun.idempotency_key == _key(order.id))
                          .with_for_update().execution_options(populate_existing=True))
    if not run or run.status != "running" or not run.input_json.get("payment_submitted"):
        raise HTTPException(409, "Payment submission requires reconciliation")
    run.input_json = {**run.input_json, "submitted_invoice_id": invoice_id}


def _progress(order, state):
    return {**payments._payment_status_payload(order), "checkout_progress": state,
            "amount_rubles": None, "can_retry": False}


def _manager_ack(order, accept_pending_amount):
    if (order.payment_method == "later" and payments.checkout_ready(order, "later")
            and payments.has_exported_reservation(order)):
        if accepted := payments._accepted_manager_order(order, accept_pending_amount):
            return accepted
        settlement = order_settlement(order)
        if not settlement or settlement.get("status") == "confirmed":
            return {**payments._payment_status_payload(order), "payment_status": "pending"}


async def checkout_response(db, order, request, *, submit=False, automatic=False, method=None,
                            accept_pending_amount=False):
    """None means an unowned, legacy request. GET never takes ownership."""
    run = await db.scalar(select(IntegrationRun).where(IntegrationRun.idempotency_key == _key(order.id)))
    if run:
        # Never combine a completed run with an order loaded before the worker committed.
        order = await get_order_by_id(db, order.id)
    if not run and not (automatic and (order.checkout_snapshot or {}).get("ms_checkout_version") == 2):
        return None
    if method and method != order.payment_method:
        raise HTTPException(409, "Order payment method has changed")
    def progress(state):
        if automatic:
            return {**_progress(order, state), "checkout_issue": public_issue(run, order)}
        if state == "processing":
            raise payments.settlement_pending()
        raise HTTPException(409, {"code": "checkout_needs_review", "message": "Checkout requires reconciliation"})

    if not run and submit and payments.checkout_ready(order, order.payment_method):
        run_id = await stage_checkout(db, order, request)
        await db.commit()
        if run_id is not None:
            await notify_worker(run_id)
        return await checkout_response(db, await get_order_by_id(db, order.id), request, automatic=True,
                                       submit=True, method=method, accept_pending_amount=accept_pending_amount)

    if order.is_paid or order.payment_status in {"paid", "refunded", "canceled"}:
        return {**payments._payment_status_payload(order), "can_retry": False}
    if order.is_canceled:
        return {**payments._payment_status_payload(order), "payment_status": "canceled", "can_retry": False}
    if order.is_shipped:
        return progress("needs_review")
    if run and (run.input_json.get("method") != order.payment_method or
                ("terms" in run.input_json and run.input_json["terms"] != _approved_terms(order))):
        return progress("needs_review")
    if automatic and run and run.status in {"error", "canceled"} and not order.payment_invoice_id:
        return progress("needs_review")
    if (automatic and run and run.status in {"queued", "retrying", "running"}
            and order.payment_method == "later"):
        return progress("processing")
    if accepted := _manager_ack(order, automatic or accept_pending_amount):
        return accepted
    if run and run.status == "running" and order.payment_status in {"created", "draft", "pending"}:
        return progress("processing")
    if not order.payment_invoice_id and (order.payment_provider == "intellectmoney" or
                                         (run and run.input_json.get("payment_submitted"))):
        return progress("needs_review")
    if order.payment_invoice_id:
        if submit and automatic:
            # POST is a local acknowledgement, even for an existing invoice.
            if run and run.status == "error":
                return progress("needs_review")
            return {**payments._payment_status_payload(order), "can_retry": False}
        result = await payments.get_payment_status_for_order(db, request=request, order=order)
        if (not result["is_paid"] and not (result.get("qr_url") or result.get("qr_image"))
                and run and result["payment_status"] in {"pending", "created", "error"}):
            return progress("processing" if run.status in {"queued", "retrying"} else "needs_review")
        return {**result, "can_retry": False}
    if run:
        if run.status in {"queued", "retrying"} and payments.checkout_ready(order, order.payment_method):
            return progress("processing")
        if (not automatic and run.status == "success" and order.payment_method == "later"
                and (order_settlement(order) or {}).get("status") == "awaiting_invoice"):
            raise payments.settlement_pending()
        return progress("needs_review")
    if submit or not payments.checkout_ready(order, order.payment_method):
        return progress("needs_review")
    return None


def _worker_request(ip):
    base = urlsplit(config.PUBLIC_API_BASE_URL or "")
    if base.scheme != "https" or not base.hostname or base.username or base.password:
        raise HTTPException(503, "A public HTTPS API origin is required for checkout")
    return Request({"type": "http", "scheme": "https", "server": (base.hostname, base.port or 443),
                    "path": "/", "root_path": "", "headers": [], "query_string": b"",
                    "client": (ip or "127.0.0.1", 0)})


def _needs_export(order):
    return (not payments.has_exported_reservation(order) or
            (order.payment_method == "sbp" and not order_settlement(order) and not order.moysklad_invoiceout_id))


async def _prepare_order(db, order, method, *, from_creation):
    from src.app.services.benefits.redemption import _bonus_application, redeem_order_bonus_safe
    if not from_creation:
        if not _needs_export(order):
            return
        previous = await db.scalar(select(IntegrationRun.status).where(
            IntegrationRun.idempotency_key == f"order:auto:moysklad:{order.id}"))
        if previous in {"queued", "retrying", "running"}:
            raise payments.settlement_pending()
        if previous in {"error", "canceled"}:
            raise HTTPException(409, "Previous export requires reconciliation")
    if not order.amocrm_lead_id:
        await payments.lock_checkout_order(db, order, method)
        await ensure_order_has_amocrm_lead(db, order, user=order.user)
        await db.commit()
    application = await _bonus_application(db, order_id=order.id)
    if application is not None and not application.external_reference:
        await payments.lock_checkout_order(db, order, method)
        if not from_creation or application.status in {"submitting", "failed", "reversed"}:
            raise HTTPException(409, "Previous bonus redemption requires reconciliation")
        application.status = "submitting"
        await db.commit()
        await payments.lock_checkout_order(db, order, method)
        if not await redeem_order_bonus_safe(db, order=order, user=order.user):
            raise HTTPException(409, "Bonus redemption requires reconciliation")
    # A standard SBP export can be interrupted between reserve and invoice commits.
    await payments.lock_checkout_order(db, order, method)
    if _needs_export(order):
        result = await sync_order_to_moysklad(db, order=order, user=order.user)
        if result.skipped_reason:
            raise HTTPException(503, f"MoySklad export not ready: {result.skipped_reason}")


async def complete_checkout(db, order_id, intent):
    method = intent.get("method")
    order = await get_order_by_id(db, order_id)
    if order is None:
        return {"skipped": "order_missing"}
    settlement = order_settlement(order)
    key = settlement["counterparty_id"] if settlement else f"order:{order_id}"
    try:
        async with payments.settlement_lock(key, payment=True):
            order = await get_order_by_id(db, order_id)
            if not payments.checkout_ready(order, method):
                if (not order.is_canceled and order.payment_status != "refunded"
                        and (order.is_paid or order.is_shipped or order.payment_status == "paid")
                        and order.amocrm_lead_id and payments.has_exported_reservation(order)):
                    return {"order_id": order_id}
                if order.is_canceled or order.is_paid or order.is_shipped or order.payment_status in {"paid", "refunded", "canceled"}:
                    return {"skipped": "superseded"}
                if (method == order.payment_method == "sbp" and order.payment_invoice_id
                        and order.amocrm_lead_id and payments.has_exported_reservation(order)
                        and intent.get("payment_submitted") and intent.get("submitted_invoice_id") == order.payment_invoice_id):
                    # A lost QR response can be recovered by reading the known invoice, never by issuing another.
                    receipt = await payments.get_payment_status_for_order(db, request=_worker_request(intent.get("ip")), order=order)
                    _require_sbp_ready(receipt)
                    return {"order_id": order_id}
                if (order.payment_provider == "intellectmoney" and not order.payment_invoice_id
                        and not (order.is_paid or order.is_canceled)):
                    raise HTTPException(409, "Invoice submission requires reconciliation")
                raise HTTPException(409, "Checkout terms or reservation changed; reconciliation required")
            if intent.get("payment_submitted"):
                raise HTTPException(409, "Payment submission requires reconciliation")
            if "terms" in intent and _approved_terms(order) != intent["terms"]:
                raise HTTPException(409, "Checkout terms have changed")
            await _prepare_order(db, order, method, from_creation=intent.get("prepare_order", False))
            await payments.lock_checkout_order(db, order, method)
            if "terms" in intent and _approved_terms(order) != intent["terms"]:
                raise HTTPException(409, "Checkout terms have changed")
            request = _worker_request(intent.get("ip")) if method == "sbp" else None
            if not order.amocrm_lead_id or not payments.has_exported_reservation(order):
                raise HTTPException(503, "MoySklad order or CRM handoff not confirmed")
            receipt = await payments._create_payment_for_order(db, request=request, order=order, payment_method=method,
                                                    accept_pending_amount=True, automatic=True)
            if method == "sbp":
                _require_sbp_ready(receipt)
    except HTTPException as exc:
        if exc.status_code == 409 and isinstance(exc.detail, dict) and exc.detail.get("code") == "settlement_pending":
            raise InvoicePreparationPending(int(exc.detail.get("retry_after_seconds") or 5)) from exc
        raise
    return {"order_id": order_id}


def _require_sbp_ready(receipt):
    if receipt.get("is_paid"):
        return
    if receipt.get("payment_status") in {"error", "canceled", "refunded", "hold", "partial"}:
        raise HTTPException(409, "Payment provider requires reconciliation")
    if not receipt.get("invoice_id"):
        raise HTTPException(409, "Invoice submission requires reconciliation")
    if not (receipt.get("qr_url") or receipt.get("qr_image")):
        raise HTTPException(503, "Waiting for payment provider QR")
