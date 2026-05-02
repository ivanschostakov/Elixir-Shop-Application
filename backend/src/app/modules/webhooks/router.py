import codecs
import re

from typing import Any
from urllib.parse import parse_qs, parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from src.app.services.orders import apply_amocrm_status_update, reconcile_sbp_payment
from src.database import get_db
from src.database.crud import get_order_by_amocrm_lead_id, get_order_by_code, get_order_by_id, get_order_by_invoice_id, update_order
from src.database.schemas import OrderUpdate
from src.integrations.amocrm import amocrm_client
from src.integrations.intellectmoney import intellectmoney

webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_INTELLECTMONEY_PAYLOAD_KEYS = {
    "eshopaccount": "EshopAccount",
    "eshopid": "EshopId",
    "hash": "Hash",
    "orderid": "OrderId",
    "paymentdata": "PaymentData",
    "paymentid": "PaymentId",
    "paymentstatus": "PaymentStatus",
    "recipientamount": "RecipientAmount",
    "recipientcurrency": "RecipientCurrency",
    "recipientoriginalamount": "RecipientOriginalAmount",
    "secretkey": "SecretKey",
    "servicename": "ServiceName",
    "useremail": "UserEmail",
    "username": "UserName",
}


def _coerce_amocrm_int(value: Any, field: str) -> int:
    raw = value or "0"
    try: return int(raw)
    except (TypeError, ValueError): return 0


def _amocrm_payload_int(payload: dict[str, list[str]], key: str) -> int:
    raw = (payload.get(key) or ["0"])[0] or "0"
    return _coerce_amocrm_int(raw, key)


def _intellectmoney_form_charset(content_type: str | None) -> str:
    match = re.search(r"(?i)(?:^|;)\s*charset\s*=\s*([^;]+)", content_type or "")
    charset = (match.group(1).strip().strip("\"'") if match else "") or "utf-8"
    if charset.lower() in {"windows-1251", "win-1251"}: charset = "cp1251"
    try: codecs.lookup(charset)
    except LookupError: return "utf-8"
    return charset


def _parse_intellectmoney_payload(body: bytes, content_type: str | None) -> tuple[dict[str, str], str]:
    charset = _intellectmoney_form_charset(content_type)
    text = body.decode(charset, "replace")
    payload: dict[str, str] = {}
    for key, value in parse_qsl(text, keep_blank_values=True, encoding=charset, errors="replace"):
        canonical_key = _INTELLECTMONEY_PAYLOAD_KEYS.get(str(key).lower(), str(key))
        payload[canonical_key] = str(value)

    return payload, charset


@webhooks_router.post("/amocrm")
async def amocrm_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    payload = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)

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
    return JSONResponse(
        {
            "ok": True,
            "order_id": updated_order.id,
            "lead_id": lead_id,
            "status_id": status_id,
        }
    )


@webhooks_router.post("/intellectmoney")
async def intellectmoney_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    content_type = request.headers.get("content-type")
    payload, _ = _parse_intellectmoney_payload(body, content_type)

    if not intellectmoney.verify_webhook_hash(payload):
        return PlainTextResponse("ERROR", status_code=400)

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
