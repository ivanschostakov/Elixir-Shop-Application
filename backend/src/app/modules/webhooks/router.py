import codecs
import logging
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

log = logging.getLogger(__name__)
webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_AMOCRM_LOG_MASKED_KEYS = {"email", "phone"}
_AMOCRM_LOG_REDACTED_KEY_PARTS = ("auth", "hash", "password", "secret", "token")
_INTELLECTMONEY_LOG_REDACTED_KEYS = {"hash", "secretkey"}
_INTELLECTMONEY_LOG_MASKED_KEYS = {"useremail", "email"}
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


def _is_amocrm_redacted_key(key: str) -> bool:
    normalized_key = str(key).lower()
    return any(part in normalized_key for part in _AMOCRM_LOG_REDACTED_KEY_PARTS)


def _mask_phone(value: str) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    return f"***{digits[-4:]}" if digits else "<masked>"


def _safe_log_value(value: str, *, max_length: int = 300) -> str:
    text = str(value)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}...<truncated {len(text) - max_length} chars>"


def _safe_amocrm_payload(payload: dict[str, list[str]]) -> dict[str, str | list[str]]:
    safe: dict[str, str | list[str]] = {}
    for key, values in sorted(payload.items()):
        normalized_key = str(key).lower()
        if _is_amocrm_redacted_key(normalized_key):
            safe[str(key)] = "<redacted>" if any(values) else ""
            continue

        safe_values: list[str] = []
        for value in values:
            if any(masked_key in normalized_key for masked_key in _AMOCRM_LOG_MASKED_KEYS):
                safe_values.append(_mask_email(value) if "email" in normalized_key else _mask_phone(value))
            else:
                safe_values.append(_safe_log_value(value))

        safe[str(key)] = safe_values[0] if len(safe_values) == 1 else safe_values
    return safe


def _safe_amocrm_body(body: bytes, *, max_length: int = 2000) -> str:
    text = body.decode("utf-8", "replace")
    text = re.sub(r"(?i)((?:[^&]*?(?:auth|hash|password|secret|token)[^&]*?)=)[^&\s]*", r"\1<redacted>", text)
    text = re.sub(r"(?i)((?:[^&]*?email[^&]*?)=)[^&\s]*", r"\1<masked>", text)
    text = re.sub(r"(?i)((?:[^&]*?phone[^&]*?)=)[^&\s]*", r"\1<masked>", text)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}...<truncated {len(text) - max_length} chars>"


def _coerce_amocrm_int(value: Any, field: str) -> int:
    raw = value or "0"
    try:
        return int(raw)
    except (TypeError, ValueError):
        log.warning("amoCRM webhook sent non-numeric field key=%s value=%s", field, raw)
        return 0


def _amocrm_payload_int(payload: dict[str, list[str]], key: str) -> int:
    raw = (payload.get(key) or ["0"])[0] or "0"
    return _coerce_amocrm_int(raw, key)


def _intellectmoney_form_charset(content_type: str | None) -> str:
    match = re.search(r"(?i)(?:^|;)\s*charset\s*=\s*([^;]+)", content_type or "")
    charset = (match.group(1).strip().strip("\"'") if match else "") or "utf-8"
    if charset.lower() in {"windows-1251", "win-1251"}:
        charset = "cp1251"
    try:
        codecs.lookup(charset)
    except LookupError:
        return "utf-8"
    return charset


def _parse_intellectmoney_payload(body: bytes, content_type: str | None) -> tuple[dict[str, str], str]:
    charset = _intellectmoney_form_charset(content_type)
    text = body.decode(charset, "replace")
    payload: dict[str, str] = {}
    for key, value in parse_qsl(text, keep_blank_values=True, encoding=charset, errors="replace"):
        canonical_key = _INTELLECTMONEY_PAYLOAD_KEYS.get(str(key).lower(), str(key))
        payload[canonical_key] = str(value)
    return payload, charset


def _mask_email(value: str) -> str:
    value = str(value or "").strip()
    if "@" not in value:
        return "<masked>" if value else ""
    local, domain = value.split("@", 1)
    local_mask = f"{local[:2]}***" if len(local) > 2 else "***"
    return f"{local_mask}@{domain}"


def _safe_intellectmoney_payload(payload: dict[str, Any]) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in sorted(payload.items()):
        normalized_key = str(key).lower()
        if normalized_key in _INTELLECTMONEY_LOG_REDACTED_KEYS:
            safe[str(key)] = "<redacted>" if value else ""
        elif normalized_key in _INTELLECTMONEY_LOG_MASKED_KEYS:
            safe[str(key)] = _mask_email(str(value))
        else:
            safe[str(key)] = str(value)
    return safe


def _safe_intellectmoney_body(body: bytes, *, charset: str = "utf-8", max_length: int = 2000) -> str:
    text = body.decode(charset, "replace")
    text = re.sub(r"(?i)((?:hash|secretkey)=)[^&\s]*", r"\1<redacted>", text)
    text = re.sub(r"(?i)((?:useremail|email)=)[^&\s]*", r"\1<masked>", text)
    text = re.sub(r'(?i)("hash"\s*:\s*")[^"]*(")', r"\1<redacted>\2", text)
    text = re.sub(r'(?i)("(?:useremail|email)"\s*:\s*")[^"]*(")', r"\1<masked>\2", text)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}...<truncated {len(text) - max_length} chars>"


@webhooks_router.post("/amocrm")
async def amocrm_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    content_type = request.headers.get("content-type")
    try:
        payload = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
    except Exception:
        log.exception(
            "Failed to parse amoCRM webhook form client=%s content_type=%s body_size=%s raw_body=%s",
            request.client.host if request.client else None,
            content_type,
            len(body),
            _safe_amocrm_body(body),
        )
        raise

    safe_payload = _safe_amocrm_payload(payload)
    safe_body = _safe_amocrm_body(body)
    client_host = request.client.host if request.client else None

    log.info(
        "amoCRM webhook received client=%s forwarded_for=%s content_type=%s body_size=%s payload=%s raw_body=%s",
        client_host,
        request.headers.get("x-forwarded-for"),
        content_type,
        len(body),
        safe_payload,
        safe_body,
    )

    lead_id = _amocrm_payload_int(payload, "leads[status][0][id]")
    status_id = _amocrm_payload_int(payload, "leads[status][0][status_id]")
    pipeline_id = _amocrm_payload_int(payload, "leads[status][0][pipeline_id]")
    log.info(
        "amoCRM webhook parsed ids lead_id=%s status_id=%s pipeline_id=%s expected_pipeline_id=%s",
        lead_id,
        status_id,
        pipeline_id,
        amocrm_client.PIPELINE_ID,
    )

    if not lead_id:
        log.warning("amoCRM webhook ignored: no lead_id payload=%s", safe_payload)
        return JSONResponse({"ok": True, "ignored": "no lead_id"})
    if pipeline_id and pipeline_id != amocrm_client.PIPELINE_ID:
        log.info(
            "amoCRM webhook ignored: wrong pipeline lead_id=%s status_id=%s pipeline_id=%s expected_pipeline_id=%s",
            lead_id,
            status_id,
            pipeline_id,
            amocrm_client.PIPELINE_ID,
        )
        return JSONResponse({"ok": True, "ignored": "wrong pipeline"})

    try:
        lead = await amocrm_client.get_lead(lead_id)
    except Exception:
        log.exception(
            "amoCRM webhook failed to fetch lead lead_id=%s status_id=%s pipeline_id=%s payload=%s",
            lead_id,
            status_id,
            pipeline_id,
            safe_payload,
        )
        raise

    name = lead.get("name") or ""
    status_id = _coerce_amocrm_int(lead.get("status_id") or status_id, "lead.status_id")
    pipeline_id = _coerce_amocrm_int(lead.get("pipeline_id") or pipeline_id, "lead.pipeline_id")
    log.info(
        "amoCRM webhook fetched lead lead_id=%s lead_name=%s status_id=%s pipeline_id=%s",
        lead_id,
        _safe_log_value(name),
        status_id,
        pipeline_id,
    )
    if pipeline_id and pipeline_id != amocrm_client.PIPELINE_ID:
        log.info(
            "amoCRM webhook ignored: fetched lead pipeline mismatch lead_id=%s status_id=%s pipeline_id=%s expected_pipeline_id=%s",
            lead_id,
            status_id,
            pipeline_id,
            amocrm_client.PIPELINE_ID,
        )
        return JSONResponse({"ok": True, "ignored": "pipeline mismatch"})

    order = await get_order_by_amocrm_lead_id(db, lead_id)
    lookup_source = "amocrm_lead_id"
    if order is None:
        match = re.search(r"№\s*([A-Za-z0-9-]+)", name)
        if match:
            public_code = match.group(1).strip().upper()
            lookup_source = "lead_name_order_code"
            order = await get_order_by_code(db, public_code)
            if order is None and public_code.isdigit():
                lookup_source = "lead_name_order_id"
                order = await get_order_by_id(db, int(public_code))

    if order is None:
        log.warning(
            "amoCRM webhook order not found lead_id=%s status_id=%s pipeline_id=%s lead_name=%s payload=%s",
            lead_id,
            status_id,
            pipeline_id,
            _safe_log_value(name),
            safe_payload,
        )
        return JSONResponse({"ok": True, "ignored": "order not found"})

    try:
        log.info(
            "amoCRM webhook matched order order_id=%s order_number=%s lead_id=%s lookup_source=%s status_id=%s",
            order.id,
            order.order_number,
            lead_id,
            lookup_source,
            status_id,
        )
        updated_order = await apply_amocrm_status_update(db, order=order, status_id=status_id)
    except Exception:
        log.exception(
            "amoCRM webhook failed while applying status order_id=%s lead_id=%s status_id=%s payload=%s",
            order.id,
            lead_id,
            status_id,
            safe_payload,
        )
        raise

    log.info(
        "amoCRM webhook applied status order_id=%s order_number=%s lead_id=%s status_id=%s order_status=%s",
        updated_order.id,
        updated_order.order_number,
        lead_id,
        status_id,
        updated_order.status,
    )
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
    charset = _intellectmoney_form_charset(content_type)
    try:
        payload, charset = _parse_intellectmoney_payload(body, content_type)
    except Exception:
        log.exception(
            "Failed to parse IntellectMoney webhook form client=%s content_type=%s body_size=%s raw_body=%s",
            request.client.host if request.client else None,
            content_type,
            len(body),
            _safe_intellectmoney_body(body, charset=charset),
        )
        raise

    safe_payload = _safe_intellectmoney_payload(payload)
    safe_body = _safe_intellectmoney_body(body, charset=charset)
    client_host = request.client.host if request.client else None

    log.info(
        "IntellectMoney webhook received client=%s forwarded_for=%s content_type=%s charset=%s body_size=%s payload=%s raw_body=%s",
        client_host,
        request.headers.get("x-forwarded-for"),
        content_type,
        charset,
        len(body),
        safe_payload,
        safe_body,
    )

    if not intellectmoney.verify_webhook_hash(payload):
        log.warning(
            "IntellectMoney webhook hash verification failed order_id=%s payment_id=%s status=%s payload=%s raw_body=%s",
            payload.get("OrderId"),
            payload.get("PaymentId"),
            payload.get("PaymentStatus"),
            safe_payload,
            safe_body,
        )
        return PlainTextResponse("ERROR", status_code=400)

    order_id_raw = payload.get("OrderId") or ""
    order = None
    lookup_source = None
    if order_id_raw:
        lookup_source = "order_code"
        order = await get_order_by_code(db, str(order_id_raw).strip().upper())
    if order is None and order_id_raw.isdigit():
        lookup_source = "order_id"
        order = await get_order_by_id(db, int(order_id_raw))
    if order is None and payload.get("PaymentId"):
        lookup_source = "payment_id"
        order = await get_order_by_invoice_id(db, str(payload["PaymentId"]))
    if order is None:
        log.warning(
            "IntellectMoney webhook order not found lookup_source=%s order_id=%s payment_id=%s payload=%s",
            lookup_source,
            order_id_raw,
            payload.get("PaymentId"),
            safe_payload,
        )
        return PlainTextResponse("ERROR", status_code=404)

    payment_status_raw = payload.get("PaymentStatus")
    payment_status_code = int(payment_status_raw) if payment_status_raw and payment_status_raw.isdigit() else None
    if payment_status_raw and payment_status_code is None:
        log.warning(
            "IntellectMoney webhook sent non-numeric payment status order_id=%s payment_id=%s payment_status=%s payload=%s",
            order.id,
            payload.get("PaymentId"),
            payment_status_raw,
            safe_payload,
        )

    try:
        log.info(
            "IntellectMoney webhook matched order order_id=%s order_number=%s lookup_source=%s payment_id=%s payment_status_code=%s",
            order.id,
            order.order_number,
            lookup_source,
            payload.get("PaymentId"),
            payment_status_code,
        )
        order = await update_order(db, order, OrderUpdate(payment_provider="intellectmoney", payment_invoice_id=payload.get("PaymentId") or None), commit=True)
        updated_order = await reconcile_sbp_payment(
            db,
            order,
            payment_status_code=payment_status_code,
            payment_data=payload.get("PaymentData"),
            invoice_id=payload.get("PaymentId"),
        )
    except Exception:
        log.exception(
            "IntellectMoney webhook failed while updating order order_id=%s payment_id=%s payment_status_code=%s payload=%s",
            order.id,
            payload.get("PaymentId"),
            payment_status_code,
            safe_payload,
        )
        raise

    log.info(
        "IntellectMoney webhook reconciled order order_id=%s order_number=%s payment_id=%s payment_status=%s is_paid=%s",
        updated_order.id,
        updated_order.order_number,
        updated_order.payment_invoice_id,
        updated_order.payment_status,
        updated_order.is_paid,
    )
    return PlainTextResponse("OK")
