from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.database.models import IntegrationRun
from .payment_rejection import PaymentRejected


async def check_failed_export(session, order, *, retry=False):
    """Only a customer POST may resume an exhausted, rate-limited export."""
    query = select(IntegrationRun).where(
        IntegrationRun.provider == "moysklad", IntegrationRun.operation == "moysklad_order_sync",
        IntegrationRun.target_type == "order", IntegrationRun.target_id == str(order.id),
    ).order_by(IntegrationRun.id.desc()).limit(1)
    run = (await session.execute(query.with_for_update() if retry else query)).scalar_one_or_none()
    if not run or run.status != "error":
        return False
    hold = (order.checkout_snapshot or {}).get("stock_reservation") or {}
    now = datetime.now(timezone.utc)
    try:
        valid_hold = hold.get("status") == "held" and datetime.fromisoformat(hold["expires_at"]) > now
    except (KeyError, TypeError, ValueError):
        valid_hold = False
    if (not valid_hold or "429 too many requests" not in (run.error or "").lower()
            or run.idempotency_key != f"order:auto:moysklad:{order.id}"
            or (run.input_json or {}).get("customer_retry")):
        raise PaymentRejected("export_failed", f"Не удалось завершить оформление заказа {order.order_number}. Сообщите его номер поддержке. Новый заказ не нужен.")
    if retry:
        run.input_json = {**(run.input_json or {}), "customer_retry": True}
        run.max_attempts = run.attempts + 1
        run.status = "retrying"
        run.finished_at = None
        run.next_attempt_at = now + timedelta(seconds=60)
        # The worker picks up due DB rows even if the queue was unavailable.
        await session.commit()
    return True
