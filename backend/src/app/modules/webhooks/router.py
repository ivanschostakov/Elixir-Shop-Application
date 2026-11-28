import hmac
import json
import logging
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

from sqlalchemy import or_, select
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse, PlainTextResponse

from sqlalchemy.ext.asyncio import AsyncSession
from src.app.services.orders import apply_amocrm_status_update, reconcile_sbp_payment
from src.app.services.rate_limit import enforce_rate_limit
from src.app.services.telegram_updates import process_telegram_update
from src.database import get_db
from src.database.crud import get_order_by_amocrm_lead_id, get_order_by_code, get_order_by_id, get_order_by_invoice_id, update_order
from src.database.crud.webhooks import payload_digest, register_webhook_delivery, claim_webhook_delivery, finish_webhook_delivery
from src.database.crud.webhooks.webhook_delivery import awaiting_amocrm_order_clause, defer_amocrm_delivery
from src.database.models import Order, WebhookDelivery
from fastapi import HTTPException
from src.database.schemas import OrderUpdate
from src.integrations.amocrm import get_amocrm_client
from src.integrations.intellectmoney import get_intellectmoney_client

from .service import _amocrm_payload_int, _amocrm_webhook_verified, _coerce_amocrm_int, _first_payload_value, _header_value, _parse_intellectmoney_payload, _request_client_ip
from .service import AMO_LINK_WINDOW, amocrm_event_time, amocrm_title_code, amocrm_transition_concern, amocrm_website_order
from config import TELEGRAM_WEBHOOK_SECRET_TOKEN, WEBHOOK_RATE_LIMIT_MAX_REQUESTS, WEBHOOK_RATE_LIMIT_WINDOW_SECONDS

webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)
amocrm_client = get_amocrm_client()
intellectmoney = get_intellectmoney_client()


def _telegram_webhook_verified(request: Request) -> bool:
    if not TELEGRAM_WEBHOOK_SECRET_TOKEN:
        return True
    token = (request.headers.get("x-telegram-bot-api-secret-token") or "").strip()
    return hmac.compare_digest(token, TELEGRAM_WEBHOOK_SECRET_TOKEN)


@webhooks_router.post("/amocrm")
async def amocrm_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(request, scope="webhooks:amocrm", limit=WEBHOOK_RATE_LIMIT_MAX_REQUESTS, window_seconds=WEBHOOK_RATE_LIMIT_WINDOW_SECONDS)
    body = await request.body()
    raw_text = body.decode("utf-8", "replace")
    log.info(
        "amoCRM webhook inbound body_bytes=%s source_ip=%s",
        len(body),
        _request_client_ip(request),
    )
    payload = parse_qs(raw_text, keep_blank_values=True)
    if not _amocrm_webhook_verified(request, payload):
        log.warning("amoCRM webhook rejected verification account_id=%s subdomain=%s source_ip=%s",_first_payload_value(payload, "account[id]"), _first_payload_value(payload, "account[subdomain]"), _request_client_ip(request))
        return JSONResponse({"ok": False, "error": "webhook verification failed"}, status_code=403)

    result = await _process_event(db, provider="amocrm", payload=payload)
    return JSONResponse(result or {"ok": True, "ignored": "duplicate"})


async def _apply_amocrm_event(db, payload, received_at):
    now = datetime.now(timezone.utc)
    if now - received_at > AMO_LINK_WINDOW:
        raise _AmoReview("receipt_outside_reconciliation_window")
    # A callback may carry multiple status records. Give each its own durable outcome.
    groups = {}
    context = {}
    for key, values in payload.items():
        match = re.fullmatch(r"leads\[status\]\[([0-9]+)\](\[.*\])", key)
        if match:
            groups.setdefault(match[1], {})[f"leads[status][0]{match[2]}"] = values
        else:
            context[key] = values
    if groups and groups.keys() != {"0"}:
        first_error = None
        for fields in groups.values():
            try:
                await _process_event(db, provider="amocrm", payload={**context, **fields}, received_at=received_at)
            except Exception as exc:
                await db.rollback()
                if first_error is None: first_error = exc
        if first_error is not None: raise first_error
        return {"ok": True, "events": len(groups)}

    lead_id = _amocrm_payload_int(payload, "leads[status][0][id]")
    status_id = _amocrm_payload_int(payload, "leads[status][0][status_id]")
    pipeline_id = _amocrm_payload_int(payload, "leads[status][0][pipeline_id]")

    if not lead_id:
        if groups: raise _AmoReview("invalid_status_lead")
        return {"ok": True, "ignored": "no lead_id"}
    if lead_id < 0 or lead_id > 2**63 - 1 or any(len(values) != 1 for fields in groups.values() for values in fields.values()):
        raise _AmoReview("invalid_status_record")
    if pipeline_id and pipeline_id != amocrm_client.PIPELINE_ID: return {"ok": True, "ignored": "wrong pipeline"}
    event_at = amocrm_event_time(payload, received_at)
    if event_at is None or now - event_at > AMO_LINK_WINDOW or event_at > now:
        raise _AmoReview("invalid_or_stale_event_time")

    order = await get_order_by_amocrm_lead_id(db, lead_id)
    if order is None:
        lead = await _current_amo_lead(lead_id)
        if lead["pipeline_id"] != amocrm_client.PIPELINE_ID:
            return {"ok": True, "ignored": "pipeline mismatch"}
        if amocrm_website_order(lead):
            # Checkout may have committed the link during the CRM read.
            order = await get_order_by_amocrm_lead_id(db, lead_id)
            if order is None:
                return {"ok": True, "ignored": "website_order"}
        else:
            public_code = amocrm_title_code(lead.get("name"))
            if public_code:
                order = await get_order_by_code(db, public_code)
                if order is not None and order.amocrm_lead_id not in (None, lead_id):
                    raise _AmoReview("conflicting_lead_link")
            if order is None:
                raise _AwaitingAmoOrder(lead_id, public_code)

    # Read current CRM state *after* taking the same order lock used by the
    # status writer. Two overlapping callbacks cannot apply snapshots in reverse.
    await db.refresh(order, with_for_update=True)
    lead = await _current_amo_lead(lead_id)
    if lead["pipeline_id"] != amocrm_client.PIPELINE_ID:
        return {"ok": True, "ignored": "pipeline mismatch"}
    if order.amocrm_lead_id != lead_id and (
        order.amocrm_lead_id is not None or amocrm_title_code(lead.get("name")) != order.order_code
    ):
        raise _AmoReview("order_identity_changed")
    if status_id != lead["status_id"]:
        raise _AmoReview("callback_not_current")
    concern = amocrm_transition_concern(
        order, previous=_amocrm_payload_int(payload, "leads[status][0][old_status_id]"),
        target=status_id, received_at=received_at, event_at=event_at,
    )
    if concern:
        raise _AmoReview(concern)

    updated_order = await apply_amocrm_status_update(db, order=order, status_id=status_id)
    return {"ok": True, "order_id": updated_order.id, "lead_id": lead_id, "status_id": status_id}


class _AwaitingAmoOrder(Exception):
    def __init__(self, lead_id, code):
        self.lookup = {"lead_id": lead_id, "code": code}


class _AmoReview(Exception):
    pass


async def _current_amo_lead(lead_id):
    lead = await amocrm_client.get_lead(lead_id)
    if not isinstance(lead, dict) or lead.get("id") != lead_id or not all(
        isinstance(lead.get(key), int) and lead[key] > 0 for key in ("pipeline_id", "status_id")
    ):
        raise HTTPException(503, "Cannot verify current CRM lead state")
    return lead


@webhooks_router.post("/intellectmoney")
async def intellectmoney_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(request, scope="webhooks:intellectmoney", limit=WEBHOOK_RATE_LIMIT_MAX_REQUESTS, window_seconds=WEBHOOK_RATE_LIMIT_WINDOW_SECONDS)
    body = await request.body()
    content_type = request.headers.get("content-type")
    payload, _ = _parse_intellectmoney_payload(body, content_type)

    if not intellectmoney.verify_webhook_hash(payload): return PlainTextResponse("ERROR", status_code=400)

    try:
        await _process_event(db, provider="intellectmoney", payload=payload)
    except HTTPException as exc:
        return PlainTextResponse("ERROR", status_code=exc.status_code)
    return PlainTextResponse("OK")


def _validate_payment_event(order, payload):
    if not intellectmoney.shop_id:
        raise HTTPException(503, "Payment merchant is not configured")
    if str(payload.get("EshopId", "")) != str(intellectmoney.shop_id):
        raise HTTPException(400, "Payment merchant mismatch")
    invoice_id = str(payload.get("PaymentId") or "")
    if not invoice_id or invoice_id != str(order.payment_invoice_id or "") or order.payment_provider != "intellectmoney":
        raise HTTPException(409, "Payment attempt mismatch")
    if str(payload.get("OrderId") or "") not in {str(order.id), str(order.order_number)}:
        raise HTTPException(400, "Payment order mismatch")
    try:
        amount = Decimal(str(payload.get("RecipientAmount")))
    except InvalidOperation as exc:
        raise HTTPException(400, "Invalid payment amount") from exc
    if (not amount.is_finite() or amount <= 0 or (amount != Decimal(order.grand_total) and payload.get("PaymentStatus") != "7")
            or amount > Decimal(order.grand_total) or str(payload.get("RecipientCurrency", "")).upper() not in {"RUB", "RUR"} or order.currency != "RUB"):
        raise HTTPException(400, "Payment amount or currency mismatch")
    if str(payload.get("PaymentStatus")) not in {"3", "4", "5", "6", "7", "8"}:
        raise HTTPException(400, "Unknown payment status")


async def _apply_intellectmoney_event(db, payload):
    order_ref = str(payload.get("OrderId") or "").strip()
    order = await get_order_by_code(db, order_ref.upper())
    if order is None and order_ref.isdigit():
        order = await get_order_by_id(db, int(order_ref))
    if order is None:
        raise HTTPException(503, "Order not available yet; retry later")
    # Serialize different events/polls of one payment before checking its attempt.
    await db.execute(select(Order.id).where(Order.id == order.id).with_for_update())
    await db.refresh(order)
    _validate_payment_event(order, payload)
    await reconcile_sbp_payment(db, order, payment_status_code=int(payload["PaymentStatus"]),
        payment_data=payload.get("PaymentData"), invoice_id=payload["PaymentId"])
    return {"ok": True}


async def _process_event(db, *, provider, payload, received_at=None):
    payload = {k: v for k, v in payload.items() if k not in {"Hash", "SecretKey"}}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    event_key = payload_digest(canonical)
    delivery_id = await claim_webhook_delivery(db, provider=provider, event_key=event_key, payload=payload,
                                              received_at=received_at)
    if delivery_id is None:
        return None
    return await _apply_claimed_event(db, delivery_id, provider, payload, received_at=received_at)


async def _apply_claimed_event(db, delivery_id, provider, payload, *, received_at=None):
    try:
        if provider == "amocrm":
            row = await db.get(WebhookDelivery, delivery_id)
            received_at = min(received_at or row.created_at, row.created_at)
            result = await _apply_amocrm_event(db, payload, received_at)
        else:
            result = await _apply_intellectmoney_event(db, payload)
    except _AmoReview as exc:
        await defer_amocrm_delivery(db, delivery_id, payload=payload, review_reason=str(exc))
        return {"ok": True, "retained": "needs_review"}
    except _AwaitingAmoOrder as exc:
        await defer_amocrm_delivery(db, delivery_id, payload=payload, lookup=exc.lookup)
        return {"ok": True, "deferred": "awaiting_order"}
    except Exception as exc:
        await db.rollback()
        # Invalid signed events are retained but cannot change payment state.
        permanent = provider == "intellectmoney" and isinstance(exc, HTTPException) and exc.status_code == 400
        await finish_webhook_delivery(db, delivery_id, error=None if permanent else exc)
        raise
    await finish_webhook_delivery(db, delivery_id)
    return result


async def retry_due_webhook_deliveries(limit=20):
    from src.database import SessionLocal
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        rows = list((await db.execute(select(WebhookDelivery).where(
            WebhookDelivery.provider.in_(["amocrm", "intellectmoney"]),
            WebhookDelivery.payload_json.is_not(None),
            WebhookDelivery.attempts < 12,
            or_(awaiting_amocrm_order_clause(),
                (WebhookDelivery.status == "awaiting_order") & (WebhookDelivery.created_at <= now - AMO_LINK_WINDOW),
                (WebhookDelivery.status == "failed") & (WebhookDelivery.next_attempt_at <= now),
                (WebhookDelivery.status == "processing") & (WebhookDelivery.lease_until <= now)),
        ).order_by(WebhookDelivery.next_attempt_at.asc().nullsfirst(), WebhookDelivery.id).limit(limit))).scalars().all())
        items = [(r.provider, r.delivery_id, r.payload_json, r.status) for r in rows]
    for provider, event_key, payload, row_status in items:
        if provider == "amocrm" and isinstance(payload.get("event"), dict):
            payload = payload["event"]
        async with SessionLocal() as db:
            try:
                delivery_id = await claim_webhook_delivery(db, provider=provider, event_key=event_key, payload=payload,
                                                          resume_waiting=row_status == "awaiting_order")
                if delivery_id is None: continue
                await _apply_claimed_event(db, delivery_id, provider, payload)
            except Exception:
                log.exception("Webhook recovery failed provider=%s", provider)
    return len(items)


@webhooks_router.post("/telegram")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(request, scope="webhooks:telegram", limit=WEBHOOK_RATE_LIMIT_MAX_REQUESTS, window_seconds=WEBHOOK_RATE_LIMIT_WINDOW_SECONDS)
    if not _telegram_webhook_verified(request):
        return JSONResponse({"ok": False, "error": "webhook verification failed"}, status_code=403)

    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"ok": False, "error": "invalid payload"}, status_code=400)

    return JSONResponse(await process_telegram_update(db, payload))
