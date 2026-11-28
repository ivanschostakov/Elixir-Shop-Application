import logging
from .payment_rejection import PaymentRejected
from .export_retry import check_failed_export
import socket
import uuid
from decimal import Decimal, InvalidOperation
from sqlalchemy import select

from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import APP_PAYMENT_RETURN_BASE_URL, INTELLECTMONEY_IP_ADDRESS, MOY_SKLAD_ORDER_SYNC_ENABLED
from src.app.services.external_errors import external_service_http_exception
from src.app.services.customer_intelligence import record_customer_event_safe
from src.app.services.benefits.redemption import reverse_order_bonus_safe
from src.database.crud import update_order
from src.database.models import Order, User
from src.database.schemas import OrderUpdate
from src.integrations.intellectmoney import IntellectMoneyError, get_intellectmoney_client
from src.integrations.moysklad.order_sync import MOY_SKLAD_INVOICEOUT_STATE_PAID, MOY_SKLAD_STATE_INVOICE_PAID, MOY_SKLAD_STATE_INVOICE_SENT, sync_moysklad_customerorder_state, sync_moysklad_invoiceout_state

from .crm import _move_lead_to_payment_result_status, _move_lead_to_pending_payment
from src.app.services.referrals.paid_orders import sync_paid_order_referral_to_app_safe
from .payment_qr_storage import build_order_payment_qr_url, find_order_payment_qr_path, save_order_payment_qr
from .payment_attempt import PaymentDocuments, payment_backoff, settlement_pending
from .settlement_payment import prepare_settlement_payment, robot_invoice_ready, settlement_lock, verify_no_unapproved_balance, verify_standard_sbp_invoice
from .stock_reservations import has_exported_reservation, require_exported_reservation, verify_remote_reservation
from src.integrations.moysklad.settlement_checkout import money, order_settlement

log = logging.getLogger(__name__)
intellectmoney = get_intellectmoney_client()

PAYMENT_STATUS_BY_CODE = {3: "created", 4: "canceled", 5: "paid", 6: "hold", 7: "partial", 8: "refunded"}
PENDING_PAYMENT_STEPS = {"", "Created", "InProcess", "SendTo3DS"}
FINAL_PAYMENT_STATUSES = {"paid", "canceled", "error", "refunded"}
DEAD_PAYMENT_STATUSES = {"canceled", "error", "refunded"}
LEGACY_PAID_PAYMENT_STATUSES = {"ok", "success"}


def _payment_status_from_step(payment_step: str | None) -> str:
    step = (payment_step or "").strip()
    if step.casefold() == "ok": return "paid"
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
    payload = {"status": "success", "order_id": order.id, "order_code": order.order_code, "order_number": order.order_number, "payment_method": order.payment_method, "payment_status": order.payment_status, "payment_step": payment_step, "invoice_id": order.payment_invoice_id, "qr_url": qr_url, "qr_image": qr_image, "is_paid": bool(order.payment_status != "refunded" and (order.is_paid or order.payment_status == "paid")), "can_retry": order.payment_status in {"canceled", "error"}, }
    payload["amount_rubles"] = float(order.grand_total)
    payload["ms_reservation_confirmed"] = (
        (order.checkout_snapshot or {}).get("ms_checkout_version") == 2
        and not order.is_canceled and has_exported_reservation(order)
    )
    payload["awaiting_settlement"] = (
        (order.payment_method or "").lower() == "sbp"
        and order.payment_status == "draft"
        and not (order.payment_invoice_id or order.is_paid or order.is_canceled)
        and order_settlement(order) is not None
    )
    if expires_at is not None: payload["expires_at"] = expires_at.replace(microsecond=0).isoformat()
    return payload


def _accepted_manager_order(order, accepts_pending_amount):
    settlement = order_settlement(order) or {}
    if (order.payment_method == "later" and order.payment_status in {"draft", "pending"}
            and order.payment_provider in {None, "manager"} and not order.payment_invoice_id
            and not order.is_paid and not order.is_canceled
            and (order.checkout_snapshot or {}).get("ms_checkout_version") == 2
            and settlement.get("status") == "awaiting_invoice"
            and has_exported_reservation(order)):
        # The verified export already includes the order total. A zero automatic
        # allowance cannot reduce it; accepting the order does not settle an invoice.
        try:
            fixed_total = (settlement.get("mode") == "automatic" and settlement.get("requested_balance_rubles") is None
                           and money(settlement.get("maximum_balance_rubles")) == 0
                           and money(settlement.get("gross_rubles")) == money(order.grand_total))
        except ValueError:
            fixed_total = False
        if fixed_total or accepts_pending_amount:
            return {**_payment_status_payload(order), "payment_status": "pending",
                    "amount_rubles": float(order.grand_total) if fixed_total else None,
                    "awaiting_settlement": not fixed_total}


def _qr_debug(value: str | None) -> dict[str, Any]:
    if not value: return {"present": False, "length": 0}
    return {"present": True, "length": len(value)}


async def _resolve_payment_qr_image(request: Request, order: Order, *, qr_image: str | None, qr_url: str | None) -> str | None:
    invoice_id = str(order.payment_invoice_id or "")
    if not invoice_id:
        return None
    try: saved_path = await save_order_payment_qr(order.user_id, order.id, invoice_id, qr_image=qr_image, qr_url=qr_url)
    except Exception:
        log.exception("Failed to save SBP QR for order %s", order.order_number)
        saved_path = find_order_payment_qr_path(order.user_id, order.id, invoice_id)

    return build_order_payment_qr_url(request, saved_path)

async def reconcile_sbp_payment(session: AsyncSession, order: Order, *, payment_step: str | None = None, payment_status_code: int | None = None, payment_data: str | None = None, invoice_id: str | None = None) -> Order:
    await session.execute(select(Order.id).where(Order.id == order.id).with_for_update())
    await session.refresh(order)
    payment_status = _payment_status_from_code(payment_status_code) or _payment_status_from_step(payment_step)
    if invoice_id and str(invoice_id) != str(order.payment_invoice_id or ""):
        raise PaymentRejected("payment_attempt_mismatch", "Payment attempt mismatch")
    previous = (order.payment_status or "").lower()
    if previous == "refunded" and payment_status != "refunded":
        return order
    if (previous == "paid" or order.is_paid) and payment_status not in {"paid", "refunded"}:
        return order
    patch: dict[str, Any] = {}

    if payment_status == "paid":

        patch["payment_status"] = "paid"
        patch["payment_paid_at"] = _parse_payment_timestamp(payment_data) or datetime.now(timezone.utc)
        patch["payment_error"] = ""
        patch["is_paid"] = True

    else:
        if payment_status == "refunded": patch["is_paid"] = False
        patch["payment_status"] = payment_status
        error_text = _payment_error_text(payment_status, payment_step)
        if error_text: patch["payment_error"] = error_text

    updated_order = await update_order(session, order, OrderUpdate(**patch), commit=False)
    from .payment_effects import queue_payment_effects, try_payment_effects
    run_id = await queue_payment_effects(session, updated_order)
    await session.commit()
    await try_payment_effects(run_id)
    if updated_order.payment_status == "refunded":
        user = await session.get(User, updated_order.user_id)
        if user is not None:
            await reverse_order_bonus_safe(session, order=updated_order, user=user)
        await sync_paid_order_referral_to_app_safe(session, order=updated_order)
    elif updated_order.payment_status == "paid" or updated_order.is_paid:
        await record_customer_event_safe(
            session,
            user_id=updated_order.user_id,
            event_name="order_paid",
            event_id=uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"elixir-shop:user:{updated_order.user_id}:order:{updated_order.id}:paid",
            ),
            entity_type="order",
            entity_id=updated_order.id,
            properties={
                "order_code": updated_order.order_code,
                "payment_method": updated_order.payment_method,
            },
            source="webhook",
            commit=True,
        )
    if updated_order.payment_status == "refunded":
        return updated_order
    if updated_order.payment_status == "paid" or updated_order.is_paid:
        await sync_paid_order_referral_to_app_safe(session, order=updated_order)
    return updated_order


async def _verify_provider_purchase(order, invoice_id):
    """The status endpoint alone contains no amount or currency."""
    info = await intellectmoney.get_purchase_info(invoice_id=invoice_id)
    result = info.get("Result") or {}
    invoice = result.get("Invoice") or {}
    shop = result.get("Eshop") or {}
    amount = invoice.get("InvoicePayerAmount") or invoice.get("TotalAmount") or {}
    try:
        valid = (str(invoice.get("InvoiceId")) == str(invoice_id)
            and str(invoice.get("OrderId")) in {str(order.id), str(order.order_number)}
            and str(shop.get("EshopId")) == str(intellectmoney.shop_id)
            and str(amount.get("Currency")).upper() in {"RUB", "RUR"}
            and Decimal(str(amount.get("Amount"))) == Decimal(order.grand_total))
    except (InvalidOperation, TypeError, ValueError):
        valid = False
    if not valid:
        raise IntellectMoneyError("Payment invoice details do not match the order")


async def _ensure_persisted_paid_state(session: AsyncSession, order: Order) -> Order:
    normalized_status = (order.payment_status or "").strip().lower()
    if normalized_status not in {"paid", *LEGACY_PAID_PAYMENT_STATUSES}:
        return order
    if order.is_paid and normalized_status == "paid" and order.payment_paid_at is not None:
        return order
    updated_order = await update_order(
        session,
        order,
        OrderUpdate(
            payment_status="paid",
            is_paid=True,
            payment_paid_at=order.payment_paid_at or order.updated_at or datetime.now(timezone.utc),
            payment_error="",
        ),
        commit=True,
    )
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
        checked_invoice_id = str(order.payment_invoice_id)
        state_result = await intellectmoney.get_bank_card_payment_state(invoice_id=checked_invoice_id)
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
            if (_payment_status_from_step(payment_step) == "paid"
                    or _payment_status_from_code(payment_status_code) in {"paid", "refunded"}):
                await _verify_provider_purchase(order, checked_invoice_id)
            order = await reconcile_sbp_payment(
                session,
                order,
                payment_step=payment_step,
                payment_status_code=payment_status_code,
                invoice_id=checked_invoice_id,
            )
    except IntellectMoneyError:
        log.warning("IntellectMoney status check failed for order %s", order.order_number)

    order = await _ensure_persisted_paid_state(session, order)
    saved_qr_image = await _resolve_payment_qr_image(request, order, qr_image=qr_image, qr_url=qr_url)
    if payment_step in PENDING_PAYMENT_STEPS and (saved_qr_image or qr_image or qr_url):
        order = await _move_lead_to_pending_payment(session, order, qr_invoice_id=checked_invoice_id)
        await _record_invoice_sent(session, order)

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
    accept_pending_amount: bool = False,
) -> dict[str, Any]:
    if (payment_method or order.payment_method) == "later":
        # Read-only acknowledgement must not wait behind the invoice worker's lock.
        if accepted := _accepted_manager_order(order, accept_pending_amount):
            return accepted
    settlement = order_settlement(order)
    lock_key = settlement["counterparty_id"] if settlement else f"order:{order.id}"
    async with settlement_lock(lock_key, payment=True):
        await session.refresh(order, attribute_names=["payment_invoice_id", "payment_status", "payment_provider", "payment_method",
            "is_paid", "is_canceled", "checkout_snapshot", "grand_total", "moysklad_customerorder_id", "moysklad_invoiceout_id"])
        return await _create_payment_for_order(session, request=request, order=order, payment_method=payment_method,
                                               accept_pending_amount=accept_pending_amount)


def _uses_standard_document_export(order: Order) -> bool:
    return MOY_SKLAD_ORDER_SYNC_ENABLED and (order.checkout_snapshot or {}).get("order_export_version") == 1


async def _record_invoice_sent(session, order):
    if ((order.checkout_snapshot or {}).get("ms_checkout_version") == 2 and order.moysklad_customerorder_id
            and order.payment_invoice_id and _uses_standard_document_export(order)):
        from .invoice_preparation import queue_invoice_sent
        await queue_invoice_sent(session, order)
    else:
        await sync_moysklad_customerorder_state(order, state_name=MOY_SKLAD_STATE_INVOICE_SENT)


async def _verify_payment_reserve(order, *, documents=None):
    try:
        await verify_remote_reservation(order, documents=documents)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "Не удалось проверить резерв в МойСклад. Повторите позже.") from exc


def _sbp_hold(order, standard):
    hold = (order.checkout_snapshot or {}).get("stock_reservation") or {}
    if hold.get("status") == "released":
        raise PaymentRejected("reservation_expired", "Время резерва истекло. Проверьте остатки и оформите заказ заново.")
    if standard and hold and (hold.get("status") != "exported" or not hold.get("remote_quantities")):
        raise PaymentRejected("reservation_unconfirmed", "Резерв ещё не подтверждён МойСкладом. Повторите через несколько секунд.")
    return hold


async def _verify_sbp_documents(session, order, settlement):
    standard = _uses_standard_document_export(order)
    hold = _sbp_hold(order, standard)
    documents = None
    if settlement:
        # Confirmation commits and can call CRM. Read stock live after that boundary.
        await prepare_settlement_payment(session, order=order)
        hold = _sbp_hold(order, standard)
    else:
        stock = standard and hold.get("status") == "exported"
        documents = PaymentDocuments(with_stock=stock,
            expand_invoices=stock and (order.checkout_snapshot or {}).get("ms_checkout_version") == 2)
        await verify_no_unapproved_balance(order, documents=documents)
        await verify_standard_sbp_invoice(order, documents=documents)
    if standard and hold:
        await _verify_payment_reserve(order, documents=documents)


def checkout_ready(order, method):
    hold = (order.checkout_snapshot or {}).get("stock_reservation") or {}
    if method == "sbp" and hold.get("expires_at"):
        try:
            if datetime.fromisoformat(hold["expires_at"]) <= datetime.now(timezone.utc):
                return False
        except (ValueError, TypeError):
            return False
    return (method in {"sbp", "later"} and order.payment_method == method
            and (order.checkout_snapshot or {}).get("ms_checkout_version") == 2
            and not (order.is_canceled or order.is_paid or order.is_shipped or order.payment_invoice_id)
            and order.payment_status in {"draft", "pending"}
            and (order.payment_provider is None or (method == "later" and order.payment_provider == "manager"))
            and hold.get("status") != "released")


async def _lock_payment_state(session, order):
    await session.refresh(order, attribute_names=[
        "payment_invoice_id", "payment_provider", "payment_method", "payment_status", "is_canceled", "is_paid",
        "is_shipped", "grand_total", "checkout_snapshot", "moysklad_customerorder_id", "moysklad_invoiceout_id",
    ], with_for_update=True)


async def lock_checkout_order(session, order, method):
    await _lock_payment_state(session, order)
    if not checkout_ready(order, method):
        raise HTTPException(409, "Checkout intent has been superseded")


def _verified_terms(order):
    return (order.grand_total, order.moysklad_customerorder_id, order.moysklad_invoiceout_id, order.checkout_snapshot)


async def _lock_provider_claim(session, order, invoice_id, terms):
    await _lock_payment_state(session, order)
    if (order.payment_provider != "intellectmoney" or order.payment_method != "sbp"
            or order.payment_invoice_id != invoice_id or order.payment_status != "created"
            or order.is_canceled or order.is_shipped or order.is_paid or _verified_terms(order) != terms):
        raise HTTPException(409, "Provider attempt has been superseded")


async def _create_payment_for_order(session: AsyncSession, *, request: Request, order: Order,
                                    payment_method: str | None = None, accept_pending_amount: bool = False,
                                    automatic: bool = False) -> dict[str, Any]:
    requested_payment_method = (payment_method or order.payment_method or "later").strip().lower()
    if order.is_canceled or order.payment_status == "refunded":
        raise PaymentRejected("order_closed", "Заказ отменён или возвращён.")
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

    v2 = (order.checkout_snapshot or {}).get("ms_checkout_version") == 2
    if (v2 or _uses_standard_document_export(order)) and order.payment_method and requested_payment_method != order.payment_method:
        raise PaymentRejected("method_changed", "Заказ оформлен с другим способом оплаты. Для его изменения обратитесь в поддержку.")

    settlement = order_settlement(order)
    if requested_payment_method == "later":
        if v2:
            require_exported_reservation(order)
            if accepted := _accepted_manager_order(order, accept_pending_amount):
                return accepted
        if settlement and (v2 or _uses_standard_document_export(order)):
            async with payment_backoff(order.id, "later"):
                await prepare_settlement_payment(session, order=order)
        elif not v2 and _uses_standard_document_export(order):
            order.moysklad_invoiceout_id = await verify_standard_sbp_invoice(order, discover_linked=True)
        if automatic:
            await lock_checkout_order(session, order, "later")
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

    if ((settlement or _uses_standard_document_export(order))
            and order.payment_provider == "intellectmoney" and not order.payment_invoice_id
            and order.payment_status in {"created", "error"}):
        raise PaymentRejected("previous_attempt_unconfirmed", "Не удалось подтвердить статус предыдущей попытки оплаты. Обратитесь в поддержку, чтобы не создать второй счёт.")
    if v2:
        require_exported_reservation(order)
        if not _uses_standard_document_export(order):
            raise settlement_pending()
    if automatic and not settlement:
        # Document reads can be slow. A cancellation may land during them;
        # the row-locked compare below is the actual payment decision.
        await session.commit()
    async with payment_backoff(order.id, "sbp"):
        await _verify_sbp_documents(session, order, settlement)
    if automatic:
        terms = _verified_terms(order)
        await lock_checkout_order(session, order, "sbp")
        if terms != _verified_terms(order):
            raise HTTPException(409, "Verified checkout documents have changed")
        from .automatic_checkout import claim_payment
        await claim_payment(session, order)
    if settlement and order.grand_total == 0:
        order = await update_order(session, order, OrderUpdate(
            payment_method="sbp", payment_provider="moysklad_balance", payment_invoice_id=None), commit=False)
        order = await reconcile_sbp_payment(session, order, payment_status_code=5)
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

    invoice_id = None
    try:
        if automatic:
            await _lock_provider_claim(session, order, None, terms)
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

        if automatic:
            from .automatic_checkout import bind_checkout_invoice
            await bind_checkout_invoice(session, order, invoice_id)
        order = await update_order(session, order, OrderUpdate(payment_invoice_id=invoice_id), commit=True)
        if automatic:
            await _lock_provider_claim(session, order, invoice_id, terms)
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

        if payment_step not in PENDING_PAYMENT_STEPS:
            if _payment_status_from_step(payment_step) == "paid":
                await _verify_provider_purchase(order, invoice_id)
            order = await reconcile_sbp_payment(session, order, payment_step=payment_step, invoice_id=invoice_id)
        else:
            order = await update_order( session, order, OrderUpdate(payment_status=_payment_status_from_step(payment_step)), commit=True)
            if saved_qr_image or qr_image or qr_url:
                order = await _move_lead_to_pending_payment(session, order, qr_invoice_id=invoice_id)
                await _record_invoice_sent(session, order)

        return _payment_status_payload(order, payment_step=payment_step, qr_url=qr_url, qr_image=saved_qr_image or qr_image, expires_at=expires_at)

    except IntellectMoneyError as exc:
        if automatic:
            if invoice_id and order.payment_invoice_id == invoice_id:
                raise HTTPException(503, "Waiting for payment provider QR") from exc
            raise HTTPException(409, "Provider submission requires reconciliation") from exc
        await update_order(session, order, OrderUpdate(payment_status="error", payment_error="Платежный провайдер временно недоступен"), commit=True)
        raise external_service_http_exception(service="intellectmoney", operation="create_payment_for_order", public_detail="Payment provider is temporarily unavailable", raw_detail=str(exc), exc=exc) from exc

    except Exception as exc:
        log.exception("Failed to initialize SBP payment for order %s", order.order_number)
        if automatic:
            if isinstance(exc, HTTPException):
                raise
            if invoice_id and order.payment_invoice_id == invoice_id:
                raise HTTPException(503, "Waiting for payment provider QR") from exc
            raise HTTPException(409, "Provider submission requires reconciliation") from exc
        await update_order(session, order, OrderUpdate(payment_status="error", payment_error="Не удалось инициализировать СБП"), commit=True)
        raise external_service_http_exception(service="intellectmoney", operation="create_payment_for_order", public_detail="Failed to initialize SBP payment", raw_detail=str(exc), exc=exc) from exc


async def get_payment_status_for_order(session: AsyncSession, *, request: Request, order: Order,
                                       accept_pending_amount: bool = False, check_invoice: bool = False) -> dict[str, Any]:
    if check_invoice and order.is_canceled and not order.is_paid:
        return {**_payment_status_payload(order), "payment_status": "canceled", "can_retry": False}
    if (check_invoice and not order.is_paid and not order.payment_invoice_id
            and order.payment_status in {"draft", "pending"}):
        settlement = order_settlement(order)
        if _uses_standard_document_export(order) and not order.moysklad_customerorder_id:
            retryable = await check_failed_export(session, order)
            return {**_payment_status_payload(order), "invoice_ready": False, "awaiting_settlement": True,
                    "export_retry_available": retryable}
        if settlement and (settlement.get("status") != "confirmed" or order.payment_method == "sbp"):
            ready = await robot_invoice_ready(order, settlement)
            return {**_payment_status_payload(order), "invoice_ready": ready, "awaiting_settlement": not ready}
        if order.payment_method == "sbp" and _uses_standard_document_export(order):
            ready = bool(order.moysklad_customerorder_id and order.moysklad_invoiceout_id)
            if ready:
                await verify_standard_sbp_invoice(order)
            return {**_payment_status_payload(order), "invoice_ready": ready, "awaiting_settlement": not ready}
        if order.payment_method == "later" and _uses_standard_document_export(order):
            if not settlement:
                await verify_standard_sbp_invoice(order, discover_linked=True)
            return {**_payment_status_payload(order), "invoice_ready": True}
    if ((order.checkout_snapshot or {}).get("ms_checkout_version") == 2
            and order.payment_method == "later" and order.payment_status in {"draft", "pending"}
            and not order.is_canceled and not order.is_paid and not order.payment_invoice_id):
        require_exported_reservation(order)
        if accepted := _accepted_manager_order(order, accept_pending_amount):
            return accepted
        settlement = order_settlement(order)
        if settlement and settlement.get("status") != "confirmed":
            raise settlement_pending()
    if (
        (order.payment_method or "").lower() == "sbp"
        and order.payment_invoice_id
        and (order.payment_status or "").strip().lower() not in FINAL_PAYMENT_STATUSES | LEGACY_PAID_PAYMENT_STATUSES
    ):
        payload, _ = await _checked_sbp_payment_payload(session, request=request, order=order)
        return payload

    order = await _ensure_persisted_paid_state(session, order)
    if order.is_paid:
        await sync_paid_order_referral_to_app_safe(session, order=order)
    saved_qr_image = await _resolve_payment_qr_image(request, order, qr_image=None, qr_url=None)
    return _payment_status_payload(order, qr_image=saved_qr_image)


async def recheck_payment_status_for_admin(session: AsyncSession, *, order: Order) -> dict[str, Any]:
    """Reconcile an order from the payment provider without allowing a manual result override."""
    if order.is_paid or order.payment_status == "paid":
        await sync_paid_order_referral_to_app_safe(session, order=order)
        return {
            "order_id": order.id,
            "invoice_id": order.payment_invoice_id,
            "payment_status": "paid",
            "already_final": True,
        }
    if (order.payment_method or "").strip().lower() != "sbp":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only SBP payments can be checked automatically")
    if not order.payment_invoice_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order has no payment invoice")

    state_result = await intellectmoney.get_bank_card_payment_state(invoice_id=str(order.payment_invoice_id))
    parsed_state = intellectmoney.parse_payment_state(state_result)
    payment_step = parsed_state["payment_step"]
    result_payload = state_result.get("Result") or {}
    payment_status_raw = result_payload.get("PaymentStatus") if isinstance(result_payload, dict) else None
    try:
        payment_status_code = int(payment_status_raw) if payment_status_raw not in (None, "") else None
    except (TypeError, ValueError):
        payment_status_code = None
    if not payment_step and payment_status_code is None:
        raise RuntimeError("Payment provider response did not contain a status")

    previous_status = order.payment_status
    checked_invoice_id = str(order.payment_invoice_id)
    if (_payment_status_from_step(payment_step) == "paid"
            or _payment_status_from_code(payment_status_code) in {"paid", "refunded"}):
        await _verify_provider_purchase(order, checked_invoice_id)
    updated_order = await reconcile_sbp_payment(
        session,
        order,
        payment_step=payment_step,
        payment_status_code=payment_status_code,
        invoice_id=str(order.payment_invoice_id),
    )
    return {
        "order_id": order.id,
        "invoice_id": order.payment_invoice_id,
        "provider_status_code": payment_status_code,
        "provider_step": payment_step,
        "previous_payment_status": previous_status,
        "payment_status": updated_order.payment_status,
        "is_paid": bool(updated_order.is_paid),
    }
