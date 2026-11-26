"""A mobile-only promotion, not a payment into the customer's shared wallet."""
from datetime import timedelta
from decimal import Decimal, ROUND_DOWN

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert

from config import ufa_now
from src.database.models import LoyaltyBonusCredit, Order, OrderBenefitApplication

KIND = "app_welcome"
FACE_VALUE = 1000


async def grant_on_email_confirmation(db, user):
    if not user.email or user.welcome_bonus_granted_at is not None:
        return
    now = ufa_now()
    # Share the historical key: never issue a second welcome credit at cutover.
    stmt = insert(LoyaltyBonusCredit).values(user_id=user.id, source_kind=KIND,
        idempotency_key=f"welcome:user:{user.id}", points=FACE_VALUE, status="local",
        earned_at=now, available_at=now, expires_at=now + timedelta(days=5))
    inserted = await db.scalar(stmt.on_conflict_do_nothing(index_elements=["idempotency_key"])
                               .returning(LoyaltyBonusCredit.id))
    if inserted is not None:
        user.welcome_bonus_granted_at = now


async def wallet(db, user_id, *, lock=False):
    stmt = select(LoyaltyBonusCredit).where(LoyaltyBonusCredit.idempotency_key == f"welcome:user:{user_id}",
        LoyaltyBonusCredit.source_kind == KIND, LoyaltyBonusCredit.status == "local")
    credit = await db.scalar(stmt.with_for_update() if lock else stmt)
    if credit is None or credit.expires_at <= ufa_now():
        return None, Decimal("0")
    # A canceled unpaid order without a live gateway invoice no longer holds
    # the discount. Keep all paid and potentially collectible orders charged.
    used = await db.scalar(select(func.sum(OrderBenefitApplication.discount_amount))
        .join(Order, Order.id == OrderBenefitApplication.order_id)
        .where(OrderBenefitApplication.user_id == user_id, OrderBenefitApplication.source_kind == KIND,
               or_(Order.is_canceled.is_(False), Order.is_paid.is_(True), Order.payment_paid_at.is_not(None),
                   Order.payment_invoice_id.is_not(None))))
    return credit, max(Decimal("0"), credit.points - (used or Decimal("0")))


def discount(available, goods):
    return min(available, (goods / 2).quantize(Decimal("0.01"), rounding=ROUND_DOWN))


async def verify_reservation(db, user_id, amount):
    _, available = await wallet(db, user_id, lock=True)
    if amount > available:
        raise HTTPException(409, "Остаток приветственных бонусов изменился. Обновите заказ.")
