"""Customer-facing lifecycle for the durable checkout job, not the payment itself."""
from datetime import datetime, timedelta, timezone
from sqlalchemy.dialects.postgresql import insert

from src.database.models import IntegrationRun, Order, User
from src.database.models.orders.history import STATUS_LABELS_BY_CODE


OPERATION = "complete_mobile_checkout"
NOTICE = "notify_checkout_result"
WINDOW = timedelta(hours=1)


def is_checkout(run):
    return run.provider == "app" and run.operation == OPERATION and run.target_type == "order"

def has_hour_window(run):
    return is_checkout(run) or (run.provider == "moysklad" and run.operation == "moysklad_order_sync"
        and run.target_type == "order" and run.idempotency_key == f"order:auto:moysklad:{run.target_id}")


def deadline(run):
    return run.started_at + WINDOW


def can_attempt(run, now):
    return now < deadline(run) if has_hour_window(run) else run.attempts < run.max_attempts


def public_issue(run, order=None):
    if not run or run.status == "success" or (not run.error and run.status not in {"error", "canceled"}):
        return None
    # Only fixed messages leave the server: provider errors can contain URLs or customer data.
    error = (run.error or "").casefold()
    if "429" in error or "too many requests" in error:
        if "moysklad" in error or "мойсклад" in error:
            code, message = "MS_429", "МойСклад временно ограничил число запросов (429)."
            if "/entity/country" in error:
                message += " Не удалось получить страну для заказа."
        else:
            code, message = "RATE_LIMIT", "Сервис оформления временно ограничил число запросов (429)."
    elif "контакт" in error or "amocrm" in error or "амосрм" in error:
        code, message = "CRM_CONTACT", "Не удалось подтвердить данные сделки в amoCRM."
        if "неоднознач" in error:
            message = "В amoCRM найдено несколько подходящих контактов покупателя."
    elif "reservation_expired" in error or "резерв" in error or "stock" in error:
        code, message = "STOCK", "Не удалось подтвердить резерв товаров."
    elif any(word in error for word in ("referrer", "referral", "промокод")):
        code, message = "PROMO", "Не удалось подтвердить привязку промокода к покупателю в МойСкладе."
    elif "terms" in error or "сумм" in error or "баланс" in error:
        code, message = "TOTAL", "Не удалось подтвердить сумму заказа или списания бонусов."
    elif "submission" in error or "provider" in error or "intellectmoney" in error or "qr" in error:
        code, message = "PAYMENT", "Платёжный сервис не подтвердил подготовку оплаты."
    elif "invoice" in error or "счёт" in error:
        code, message = "MS_INVOICE", "Не удалось подтвердить счёт по заказу."
    elif "moysklad" in error or "мойсклад" in error:
        code, message = "MS_EXPORT", "МойСклад не подтвердил выгрузку заказа."
    elif "timeout" in error or "timed out" in error:
        code, message = "TIMEOUT", "Сервис оформления не ответил вовремя."
    elif "worker" in error or "deadline" in error:
        code, message = "CHECKOUT_TIMEOUT", "Обработчик не успел завершить оформление."
    elif order is not None and not order.amocrm_lead_id:
        code, message = "CRM_CONTACT", "Не удалось подтвердить создание сделки в amoCRM."
    elif order is not None and not order.moysklad_customerorder_id:
        code, message = "MS_EXPORT", "Не удалось подтвердить создание заказа в МойСкладе."
    elif order is not None and order.payment_method == "sbp":
        code, message = "PAYMENT", "Не удалось завершить подготовку платежа СБП."
    else:
        code, message = "CHECKOUT_REVIEW", "Сервер не подтвердил завершение оформления."
    retrying = run.status in {"queued", "running", "retrying"} and datetime.now(timezone.utc) < deadline(run)
    return {"code": code, "message": message, "retrying": retrying, "retry_until": deadline(run)}


async def record_state(db, run, state):
    if not is_checkout(run):
        return
    order = await db.get(Order, int(run.target_id), with_for_update=True)
    if not order or order.is_canceled or order.payment_status == "refunded":
        return
    # Preserve later fulfillment states set by the CRM.
    if not order.is_shipped and not order.is_paid and order.status in {
        STATUS_LABELS_BY_CODE[k][0] for k in ("created", "processing", "checkout_failed")
    }:
        order.status = STATUS_LABELS_BY_CODE[state][0]
    if state == "processing":
        hold = (order.checkout_snapshot or {}).get("stock_reservation", {})
        if hold.get("status") == "held" and hold.get("expires_at"):
            ends = datetime.fromisoformat(hold["expires_at"])
            if datetime.now(timezone.utc) < ends < deadline(run):
                order.checkout_snapshot = {**order.checkout_snapshot, "stock_reservation": {
                    **hold, "expires_at": deadline(run).isoformat()}}
        return
    await db.execute(insert(IntegrationRun).values(
        provider="app", operation=NOTICE, target_type="order", target_id=str(order.id),
        idempotency_key=f"app:checkout-notice:{run.id}:{state}", input_json={"state": state},
        status="queued", attempts=0, max_attempts=6, counters_json={},
        next_attempt_at=datetime.now(timezone.utc),
    ).on_conflict_do_nothing(index_elements=[IntegrationRun.idempotency_key]))


async def notify_result(db, order_id, state):
    from src.app.services.push_notifications import send_push_to_user
    order = await db.get(Order, order_id)
    if not order or order.is_canceled:
        return {"sent": False}
    ok = state == "created"
    if ok:
        from .checkout_readiness import record_created_when_ready
        await record_created_when_ready(db, order, verified_checkout=True)
    title = f"Заказ №{order.order_number}"
    body = "Заказ оформлен." if ok else "Не удалось завершить оформление. Причина указана в истории заказов."
    sent = await send_push_to_user(db, user_id=order.user_id, title=title, body=body, checkout_result=True,
        data={"type": "order_status_changed", "order_id": order.id, "order_number": order.order_number,
              "status_code": state, "history_bucket": "active"})
    if sent:
        return {"sent": True, "channel": "push"}
    buyer = await db.get(User, order.user_id)
    if buyer and buyer.is_verified and buyer.email:
        from src.app.services.email_verification import send_checkout_result_email
        await send_checkout_result_email(to_email=buyer.email, subject=title, body=body)
        return {"sent": True, "channel": "email"}
    return {"sent": False, "reason": "no_verified_channel"}
