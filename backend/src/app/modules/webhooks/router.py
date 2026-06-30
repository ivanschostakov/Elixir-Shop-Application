import hmac
import json
import logging
import re
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse, PlainTextResponse

from sqlalchemy.ext.asyncio import AsyncSession
from src.app.services.orders import apply_amocrm_status_update, reconcile_sbp_payment
from src.app.services.rate_limit import enforce_rate_limit
from src.app.services.telegram_updates import process_telegram_update
from src.database import get_db
from src.database.crud import get_order_by_amocrm_lead_id, get_order_by_code, get_order_by_id, get_order_by_invoice_id, update_order
from src.database.crud.webhooks import payload_digest, register_webhook_delivery
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
    log.info("amoCRM webhook inbound headers=%s body=%s", dict(request.headers), raw_text)
    payload = parse_qs(raw_text, keep_blank_values=True)
    if not _amocrm_webhook_verified(request, payload):
        log.warning("amoCRM webhook rejected verification account_id=%s subdomain=%s source_ip=%s",_first_payload_value(payload, "account[id]"), _first_payload_value(payload, "account[subdomain]"), _request_client_ip(request))
        return JSONResponse({"ok": False, "error": "webhook verification failed"}, status_code=403)

    delivery_id = _header_value(request, "x-delivery-id", "x-request-id", "x-webhook-id", "x-amocrm-delivery-id")
    signature = _header_value(request, "x-amocrm-signature", "x-signature", "x-hub-signature", "x-hub-signature-256")
    signature_timestamp = _header_value(request, "x-signature-timestamp", "x-amocrm-signature-timestamp", "x-timestamp")
    if signature_timestamp is None: signature_timestamp = (payload.get("timestamp") or [None])[0]
    accepted = await register_webhook_delivery(db, provider="amocrm", delivery_id=delivery_id, signature=signature, signature_timestamp=signature_timestamp, payload_hash=payload_digest(body))
    if not accepted: return JSONResponse({"ok": True, "ignored": "duplicate"})

    lead_id = _amocrm_payload_int(payload, "leads[status][0][id]")
    status_id = _amocrm_payload_int(payload, "leads[status][0][status_id]")
    pipeline_id = _amocrm_payload_int(payload, "leads[status][0][pipeline_id]")

    if not lead_id: return JSONResponse({"ok": True, "ignored": "no lead_id"})
    if pipeline_id and pipeline_id != amocrm_client.PIPELINE_ID: return JSONResponse({"ok": True, "ignored": "wrong pipeline"})

    lead = await amocrm_client.get_lead(lead_id)
    name = lead.get("name") or ""
    status_id = _coerce_amocrm_int(lead.get("status_id") or status_id, "lead.status_id")
    pipeline_id = _coerce_amocrm_int(lead.get("pipeline_id") or pipeline_id, "lead.pipeline_id")
    if pipeline_id and pipeline_id != amocrm_client.PIPELINE_ID: return JSONResponse({"ok": True, "ignored": "pipeline mismatch"})

    order = await get_order_by_amocrm_lead_id(db, lead_id)
    if order is None:
        match = re.search(r"№\s*([A-Za-z0-9-]+)", name)
        if match:
            public_code = match.group(1).strip().upper()
            order = await get_order_by_code(db, public_code)
            if order is None and public_code.isdigit(): order = await get_order_by_id(db, int(public_code))

    if order is None: return JSONResponse({"ok": True, "ignored": "order not found"})

    updated_order = await apply_amocrm_status_update(db, order=order, status_id=status_id)
    return JSONResponse({
        "ok": True,
        "order_id": updated_order.id,
        "lead_id": lead_id,
        "status_id": status_id,
    })


@webhooks_router.post("/intellectmoney")
async def intellectmoney_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(request, scope="webhooks:intellectmoney", limit=WEBHOOK_RATE_LIMIT_MAX_REQUESTS, window_seconds=WEBHOOK_RATE_LIMIT_WINDOW_SECONDS)
    body = await request.body()
    content_type = request.headers.get("content-type")
    payload, _ = _parse_intellectmoney_payload(body, content_type)

    if not intellectmoney.verify_webhook_hash(payload): return PlainTextResponse("ERROR", status_code=400)

    delivery_id = _header_value(request, "x-delivery-id", "x-request-id", "x-webhook-id")
    if not delivery_id: delivery_id = payload.get("PaymentId") or payload.get("OrderId")
    signature = payload.get("Hash")
    signature_timestamp = payload.get("PaymentData")
    accepted = await register_webhook_delivery(db, provider="intellectmoney", delivery_id=delivery_id, signature=signature, signature_timestamp=signature_timestamp, payload_hash=payload_digest(body))
    if not accepted: return PlainTextResponse("OK")

    order_id_raw = payload.get("OrderId") or ""
    order = None
    if order_id_raw: order = await get_order_by_code(db, str(order_id_raw).strip().upper())
    if order is None and order_id_raw.isdigit(): order = await get_order_by_id(db, int(order_id_raw))
    if order is None and payload.get("PaymentId"): order = await get_order_by_invoice_id(db, str(payload["PaymentId"]))
    if order is None: return PlainTextResponse("ERROR", status_code=404)

    payment_status_raw = payload.get("PaymentStatus")
    payment_status_code = int(payment_status_raw) if payment_status_raw and payment_status_raw.isdigit() else None
    order = await update_order(db, order, OrderUpdate(payment_provider="intellectmoney", payment_invoice_id=payload.get("PaymentId") or None), commit=True)
    await reconcile_sbp_payment(db, order, payment_status_code=payment_status_code, payment_data=payload.get("PaymentData"), invoice_id=payload.get("PaymentId"))
    return PlainTextResponse("OK")


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
