import logging
import socket

from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import APP_PAYMENT_RETURN_BASE_URL, INTELLECTMONEY_IP_ADDRESS
from src.app.services.external_errors import external_service_http_exception
from src.database.crud import update_order
from src.database.models import Order
from src.database.schemas import OrderUpdate
from src.integrations.intellectmoney import IntellectMoneyError, get_intellectmoney_client
from src.integrations.moysklad.order_sync import MOY_SKLAD_INVOICEOUT_STATE_PAID, MOY_SKLAD_STATE_INVOICE_PAID, MOY_SKLAD_STATE_INVOICE_SENT, sync_moysklad_customerorder_state, sync_moysklad_invoiceout_state

from .crm import _move_lead_to_payment_result_status, _move_lead_to_pending_payment
from .payment_qr_storage import build_order_payment_qr_url, find_order_payment_qr_path, save_order_payment_qr

log = logging.getLogger(__name__)
intellectmoney = get_intellectmoney_client()

PAYMENT_STATUS_BY_CODE = {3: "created", 4: "canceled", 5: "paid", 6: "hold", 7: "partial", 8: "refunded"}
PENDING_PAYMENT_STEPS = {"", "Created", "InProcess", "SendTo3DS"}
FINAL_PAYMENT_STATUSES = {"paid", "canceled", "error", "refunded"}
DEAD_PAYMENT_STATUSES = {"canceled", "error", "refunded"}


def _payment_status_from_step(payment_step: str | None) -> str:
    step = (payment_step or "").strip()
    if step == "OK": return "paid"
    if step == "Error": return "error"
    if step in PENDING_PAYMENT_STEPS: return "pending"
    return step.lower() if step else "pending"


def _payment_status_from_code(payment_status_code: int | None) -> str | None:
    if payment_status_code is None: return None
    return PAYMENT_STATUS_BY_CODE.get(int(payment_status_code))


def _parse_payment_timestamp(value: str | None) -> datetime | None:
    if not value: return None
    raw = str(value).strip()
    if not raw: return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try: return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError: continue

    try: dt = datetime.fromisoformat(raw)
    except ValueError: return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _payment_error_text(payment_status: str | None, payment_step: str | None = None) -> str | None:
    if payment_status == "canceled": return "Платеж был отменен"
    if payment_status == "error": return "Ошибка оплаты"
    if payment_status == "refunded": return "Платеж возвращен"
    if payment_status == "hold": return "Платеж захолдирован"
    if payment_status == "partial": return "Платеж оплачен частично"
    if payment_step and payment_step not in PENDING_PAYMENT_STEPS: return payment_step
    return None

def _base_return_url(request: Request) -> str:
    configured = (APP_PAYMENT_RETURN_BASE_URL or "").strip().rstrip("/")
    if configured: return configured
    return str(request.base_url).rstrip("/")


def _intellectmoney_urls(request: Request, order_id: int) -> dict[str, str]:
    base = _base_return_url(request)
    api_base = str(request.base_url).rstrip("/")
    fallback_url = f"{base}/payment?orderId={order_id}"
    return {"success_url": fallback_url, "fail_url": fallback_url, "back_url": fallback_url, "result_url": f"{api_base}/api/v1/webhooks/intellectmoney", }


def _ipv4_from_value(value: str | None) -> str | None:
    if not value: return None
    for raw_candidate in str(value).split(","):
        candidate = raw_candidate.strip().strip('"').strip("'")
        if not candidate: continue
        if candidate.lower().startswith("for="): candidate = candidate[4:].strip().strip('"').strip("'")
        if candidate.startswith("[") and "]" in candidate: candidate = candidate[1:candidate.index("]")]
        elif candidate.count(":") == 1 and "." in candidate: candidate = candidate.rsplit(":", 1)[0]
        try: parsed = ip_address(candidate)
        except ValueError: continue
        if parsed.version == 4: return str(parsed)
        
    return None


def _detect_request_ip(request: Request) -> str:
    configured_ip = _ipv4_from_value(INTELLECTMONEY_IP_ADDRESS)
    if configured_ip: return configured_ip
    if INTELLECTMONEY_IP_ADDRESS:
        log.warning("Ignoring invalid INTELLECTMONEY_IP_ADDRESS=%s; expected IPv4", INTELLECTMONEY_IP_ADDRESS)

    for header_name in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for", "forwarded"):
        header_ip = _ipv4_from_value(request.headers.get(header_name))
        if header_ip: return header_ip

    if request.client and request.client.host:
        client_ip = _ipv4_from_value(request.client.host)
        if client_ip: return client_ip

    host = urlsplit(_base_return_url(request)).hostname
    if host:
        try: return socket.gethostbyname(host)
        except OSError: log.warning("Unable to resolve return base host %s for IntellectMoney; falling back", host)

    return "127.0.0.1"

def _payment_status_payload(order: Order, *, payment_step: str | None = None, qr_url: str | None = None, qr_image: str | None = None, expires_at: datetime | None = None) -> dict[str, Any]:
    payload = {"status": "success", "order_id": order.id, "order_code": order.order_code, "order_number": order.order_number, "payment_method": order.payment_method, "payment_status": order.payment_status, "payment_step": payment_step, "invoice_id": order.payment_invoice_id, "qr_url": qr_url, "qr_image": qr_image, "is_paid": bool(order.is_paid or order.payment_status == "paid"), "can_retry": order.payment_status in {"canceled", "error"}, }
    if expires_at is not None: payload["expires_at"] = expires_at.replace(microsecond=0).isoformat()
    return payload


def _qr_debug(value: str | None) -> dict[str, Any]:
    if not value: return {"present": False, "length": 0}
    return {"present": True, "length": len(value)}


async def _resolve_payment_qr_image(request: Request, order: Order, *, qr_image: str | None, qr_url: str | None) -> str | None:
    try: saved_path = await save_order_payment_qr(order.user_id, order.id, qr_image=qr_image, qr_url=qr_url)
    except Exception:
        log.exception("Failed to save SBP QR for order %s", order.order_number)
        saved_path = find_order_payment_qr_path(order.user_id, order.id)

    return build_order_payment_qr_url(request, saved_path)

async def reconcile_sbp_payment(session: AsyncSession, order: Order, *, payment_step: str | None = None, payment_status_code: int | None = None, payment_data: str | None = None, invoice_id: str | None = None) -> Order:
    payment_status = _payment_status_from_code(payment_status_code) or _payment_status_from_step(payment_step)
    patch: dict[str, Any] = {}
    if invoice_id: patch["payment_invoice_id"] = str(invoice_id)

    if payment_status == "paid":
        order = await _move_lead_to_payment_result_status(session, order, payment_status=payment_status)
        patch["payment_status"] = "paid"
        patch["payment_paid_at"] = _parse_payment_timestamp(payment_data) or datetime.now(timezone.utc)
        patch["payment_error"] = ""
        patch["is_paid"] = True

    else:
        if payment_status in {"canceled", "error", "refunded", "hold", "partial"}: order = await _move_lead_to_payment_result_status(session, order, payment_status=payment_status)
        patch["payment_status"] = payment_status
        error_text = _payment_error_text(payment_status, payment_step)
        if error_text: patch["payment_error"] = error_text

    updated_order = await update_order(session, order, OrderUpdate(**patch), commit=True)
    if updated_order.payment_status == "paid" or updated_order.is_paid:
        await sync_moysklad_customerorder_state(updated_order, state_name=MOY_SKLAD_STATE_INVOICE_PAID)
        await sync_moysklad_invoiceout_state(updated_order, state_name=MOY_SKLAD_INVOICEOUT_STATE_PAID)
    return updated_order


async def _ensure_persisted_paid_state(session: AsyncSession, order: Order) -> Order:
    if order.payment_status != "paid" or order.is_paid: return order
    updated_order = await update_order(session, order, OrderUpdate(is_paid=True), commit=True)
    return updated_order


async def _checked_sbp_payment_payload(
    session: AsyncSession,
    *,
    request: Request,
    order: Order,
) -> tuple[dict[str, Any], bool]:
    payment_step = None
    payment_status_code = None
    qr_url = None
    qr_image = None
    provider_checked = False

    try:
        state_result = await intellectmoney.get_bank_card_payment_state(invoice_id=str(order.payment_invoice_id))
        parsed_state = intellectmoney.parse_payment_state(state_result)
        provider_checked = True
        payment_step = parsed_state["payment_step"]
        result_payload = state_result.get("Result") or {}
        payment_status_raw = result_payload.get("PaymentStatus") if isinstance(result_payload, dict) else None
        try:
            payment_status_code = int(payment_status_raw) if payment_status_raw not in (None, "") else None
        except (TypeError, ValueError):
            payment_status_code = None
        qr_url = parsed_state["qr_url"]
        qr_image = parsed_state["qr_image"]
        log.info(
            "IntellectMoney status parsed order_number=%s invoice_id=%s payment_step=%s qr_url=%s qr_image=%s",
            order.order_number,
            order.payment_invoice_id,
            payment_step,
            qr_url,
            _qr_debug(qr_image),
        )
        if payment_step or payment_status_code is not None:
            order = await reconcile_sbp_payment(
                session,
                order,
                payment_step=payment_step,
                payment_status_code=payment_status_code,
                invoice_id=str(order.payment_invoice_id),
            )
    except IntellectMoneyError:
        log.warning("IntellectMoney status check failed for order %s", order.order_number)

    order = await _ensure_persisted_paid_state(session, order)
    saved_qr_image = await _resolve_payment_qr_image(request, order, qr_image=qr_image, qr_url=qr_url)
    if payment_step in PENDING_PAYMENT_STEPS and (saved_qr_image or qr_image or qr_url):
        order = await _move_lead_to_pending_payment(session, order)
        await sync_moysklad_customerorder_state(order, state_name=MOY_SKLAD_STATE_INVOICE_SENT)

    provider_confirmed_dead = provider_checked and (
        payment_step == "Error"
        or _payment_status_from_code(payment_status_code) in DEAD_PAYMENT_STATUSES
    )
    return (
        _payment_status_payload(
            order,
            payment_step=payment_step,
            qr_url=qr_url,
            qr_image=saved_qr_image or qr_image,
        ),
        provider_confirmed_dead,
    )


async def create_payment_for_order(
    session: AsyncSession,
    *,
    request: Request,
    order: Order,
    payment_method: str | None = None,
) -> dict[str, Any]:
    requested_payment_method = (payment_method or order.payment_method or "later").strip().lower()
    if order.is_paid or order.payment_status == "paid":
        order = await _ensure_persisted_paid_state(session, order)
        return _payment_status_payload(order)

    if requested_payment_method not in {"later", "sbp"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported payment method")

    has_existing_intellectmoney_payment = bool(
        order.payment_invoice_id
        and (
            (order.payment_provider or "").strip().lower() == "intellectmoney"
            or (order.payment_method or "").strip().lower() == "sbp"
        )
    )
    if has_existing_intellectmoney_payment:
        existing_payload, provider_confirmed_dead = await _checked_sbp_payment_payload(
            session,
            request=request,
            order=order,
        )
        if not provider_confirmed_dead:
            return existing_payload

    if requested_payment_method == "later":
        order = await update_order(
            session,
            order,
            OrderUpdate(
                payment_method="later",
                payment_provider="manager",
                payment_status="pending",
                payment_invoice_id=None,
                payment_error="",
            ),
            commit=True,
        )
        return _payment_status_payload(order)

    urls = _intellectmoney_urls(request, order.id)
    ip_address = _detect_request_ip(request)
    user_name = " ".join(part for part in [order.recipient.name, order.recipient.surname] if part).strip() or f"Заказ {order.order_number}"
    order = await update_order(
        session,
        order,
        OrderUpdate(
            payment_method="sbp",
            payment_provider="intellectmoney",
            payment_status="created",
            payment_invoice_id=None,
            payment_error="",
        ),
        commit=True,
    )

    try:
        expires_at = datetime.now() + timedelta(minutes=30)
        create_invoice_result = await intellectmoney.create_invoice(order_id=str(order.order_number), service_name=f"Заказ №{order.order_number}", amount_rub=order.grand_total, user_name=user_name, email=order.recipient.email, success_url=urls["success_url"], fail_url=urls["fail_url"], back_url=urls["back_url"], result_url=urls["result_url"], preference="Sbp")

        result_payload = create_invoice_result.get("Result") or {}
        invoice_id = str(
            result_payload.get("InvoiceId")
            or result_payload.get("invoiceId")
            or create_invoice_result.get("InvoiceId")
            or ""
        )
        log.info("IntellectMoney createInvoice parsed order_number=%s invoice_id=%s result_keys=%s", order.order_number, invoice_id, sorted(result_payload.keys()) if isinstance(result_payload, dict) else [])
        if not invoice_id: raise IntellectMoneyError("IntellectMoney createInvoice succeeded without InvoiceId")

        order = await update_order(session, order, OrderUpdate(payment_invoice_id=invoice_id), commit=True)
        sbp_result = await intellectmoney.sbp_payment(invoice_id=invoice_id, success_url=urls["success_url"], fail_url=urls["fail_url"], ip_address=ip_address)
        parsed_sbp = intellectmoney.parse_payment_state(sbp_result)
        state_result = await intellectmoney.get_bank_card_payment_state(invoice_id=invoice_id)
        parsed_state = intellectmoney.parse_payment_state(state_result)
        payment_step = parsed_state["payment_step"] or parsed_sbp["payment_step"]
        qr_url = parsed_state["qr_url"] or parsed_sbp["qr_url"]
        qr_image = parsed_state["qr_image"] or parsed_sbp["qr_image"]
        log.info(
            "IntellectMoney SBP parsed order_number=%s invoice_id=%s parsed_sbp=%s parsed_state=%s selected_payment_step=%s selected_qr_url_present=%s selected_qr_image=%s", order.order_number, invoice_id, {
            "payment_step": parsed_sbp["payment_step"], "qr_url_present": bool(parsed_sbp["qr_url"]), "qr_image": _qr_debug(parsed_sbp["qr_image"]), }, {
            "payment_step": parsed_state["payment_step"], "qr_url_present": bool(parsed_state["qr_url"]), "qr_image": _qr_debug(parsed_state["qr_image"]), }, payment_step, bool(qr_url), _qr_debug(qr_image)
        )
        saved_qr_image = await _resolve_payment_qr_image(request, order, qr_image=qr_image, qr_url=qr_url)
        log.info("IntellectMoney SBP QR resolved order_number=%s invoice_id=%s saved_qr_image=%s returned_qr_image=%s returned_qr_url_present=%s", order.order_number, invoice_id, saved_qr_image, _qr_debug(qr_image), bool(qr_url))

        if payment_step not in PENDING_PAYMENT_STEPS: order = await reconcile_sbp_payment(session, order, payment_step=payment_step, invoice_id=invoice_id)
        else:
            order = await update_order( session, order, OrderUpdate(payment_status=_payment_status_from_step(payment_step)), commit=True)
            if saved_qr_image or qr_image or qr_url:
                order = await _move_lead_to_pending_payment(session, order)
                await sync_moysklad_customerorder_state(order, state_name=MOY_SKLAD_STATE_INVOICE_SENT)

        return _payment_status_payload(order, payment_step=payment_step, qr_url=qr_url, qr_image=saved_qr_image or qr_image, expires_at=expires_at)

    except IntellectMoneyError as exc:
        await update_order(session, order, OrderUpdate(payment_status="error", payment_error="Платежный провайдер временно недоступен"), commit=True)
        raise external_service_http_exception(service="intellectmoney", operation="create_payment_for_order", public_detail="Payment provider is temporarily unavailable", raw_detail=str(exc), exc=exc) from exc

    except Exception as exc:
        log.exception("Failed to initialize SBP payment for order %s", order.order_number)
        await update_order(session, order, OrderUpdate(payment_status="error", payment_error="Не удалось инициализировать СБП"), commit=True)
        raise external_service_http_exception(service="intellectmoney", operation="create_payment_for_order", public_detail="Failed to initialize SBP payment", raw_detail=str(exc), exc=exc) from exc


async def get_payment_status_for_order(session: AsyncSession, *, request: Request, order: Order) -> dict[str, Any]:
    if (order.payment_method or "").lower() == "sbp"  and order.payment_invoice_id and (order.payment_status or "") not in FINAL_PAYMENT_STATUSES:
        payload, _ = await _checked_sbp_payment_payload(session, request=request, order=order)
        return payload

    order = await _ensure_persisted_paid_state(session, order)
    saved_qr_image = await _resolve_payment_qr_image(request, order, qr_image=None, qr_url=None)
    return _payment_status_payload(order, qr_image=saved_qr_image)
