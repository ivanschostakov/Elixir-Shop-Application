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
from src.database.models import Order, WebhookDelivery
from fastapi import HTTPException
from src.database.schemas import OrderUpdate
from src.integrations.amocrm import get_amocrm_client
from src.integrations.intellectmoney import get_intellectmoney_client

from .service import _amocrm_payload_int, _amocrm_webhook_verified, _coerce_amocrm_int, _first_payload_value, _header_value, _parse_intellectmoney_payload, _request_client_ip
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


async def _apply_amocrm_event(db, payload):
    lead_id = _amocrm_payload_int(payload, "leads[status][0][id]")
    status_id = _amocrm_payload_int(payload, "leads[status][0][status_id]")
    pipeline_id = _amocrm_payload_int(payload, "leads[status][0][pipeline_id]")

    if not lead_id: return {"ok": True, "ignored": "no lead_id"}
    if pipeline_id and pipeline_id != amocrm_client.PIPELINE_ID: return {"ok": True, "ignored": "wrong pipeline"}

    lead = await amocrm_client.get_lead(lead_id)
    name = lead.get("name") or ""
    status_id = _coerce_amocrm_int(lead.get("status_id") or status_id, "lead.status_id")
    pipeline_id = _coerce_amocrm_int(lead.get("pipeline_id") or pipeline_id, "lead.pipeline_id")
    if pipeline_id and pipeline_id != amocrm_client.PIPELINE_ID: return {"ok": True, "ignored": "pipeline mismatch"}

    order = await get_order_by_amocrm_lead_id(db, lead_id)
    if order is None:
        match = re.search(r"№\s*([A-Za-z0-9-]+)", name)
        if match:
            public_code = match.group(1).strip().upper()
            order = await get_order_by_code(db, public_code)
            if order is None and public_code.isdigit(): order = await get_order_by_id(db, int(public_code))

    if order is None: raise HTTPException(503, "Order not available yet; retry later")

    updated_order = await apply_amocrm_status_update(db, order=order, status_id=status_id)
    return {"ok": True, "order_id": updated_order.id, "lead_id": lead_id, "status_id": status_id}


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


async def _process_event(db, *, provider, payload):
    canonical = json.dumps({k: v for k, v in payload.items() if k not in {"Hash", "SecretKey"}}, sort_keys=True, separators=(",", ":")).encode()
    event_key = payload_digest(canonical)
    delivery_id = await claim_webhook_delivery(db, provider=provider, event_key=event_key,
        payload={key: value for key, value in payload.items() if key not in {"Hash", "SecretKey"}})
    if delivery_id is None:
        return None
    try:
        result = await (_apply_intellectmoney_event(db, payload) if provider == "intellectmoney" else _apply_amocrm_event(db, payload))
    except Exception as exc:
        await db.rollback()
        # Invalid signed events are retained but cannot change payment state.
        permanent = isinstance(exc, HTTPException) and exc.status_code == 400
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
            WebhookDelivery.payload_json.is_not(None), WebhookDelivery.attempts < 12,
            or_((WebhookDelivery.status == "failed") & (WebhookDelivery.next_attempt_at <= now),
                (WebhookDelivery.status == "processing") & (WebhookDelivery.lease_until <= now)),
        ).limit(limit))).scalars().all())
        items = [(r.provider, r.delivery_id, r.payload_json) for r in rows]
    for provider, event_key, payload in items:
        async with SessionLocal() as db:
            try:
                delivery_id = await claim_webhook_delivery(db, provider=provider, event_key=event_key, payload=payload)
                if delivery_id is None: continue
                try:
                    await (_apply_intellectmoney_event(db, payload) if provider == "intellectmoney" else _apply_amocrm_event(db, payload))
                except Exception as exc:
                    await db.rollback()
                    await finish_webhook_delivery(db, delivery_id, error=exc)
                    continue
                await finish_webhook_delivery(db, delivery_id)
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
