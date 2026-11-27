from fastapi import HTTPException
from sqlalchemy import func, select

from src.database.models import Order, RewardProgramSelectionEvent as Event, User


async def lock_order_referrer(db, buyer):
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"order-promo:{buyer}", 0))))


async def require_no_competing_referral(db, buyer, code):
    recorded = Order.checkout_snapshot["benefits"]["ms_order_promo"].as_string()
    # Ignore orders from a referral relationship the buyer already closed.
    cutoff = select(func.max(Event.created_at)).where(Event.user_id == User.id,
        Event.source == "promo_unlink", Event.snapshot["buyer"].as_string() == str(buyer),
        Event.snapshot["done"].as_boolean().is_(True)).correlate(User).scalar_subquery()
    conflict = await db.scalar(select(Order.id).join(User, User.id == Order.user_id).where(
        User.moysklad_counterparty_id == buyer, Order.is_canceled.is_(False),
        cutoff.is_(None) | (Order.created_at >= cutoff),
        func.lower(recorded) != code.lower()).limit(1))
    if conflict:
        raise HTTPException(409, "Другой заказ уже передан с другим промокодом. Дождитесь обновления МойСклада.")
