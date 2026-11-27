"""A mobile-only promotion, not a payment into the customer's shared wallet."""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.dialects.postgresql import insert

from config import ufa_now
from src.database.models import LoyaltyBonusCredit, Order, OrderBenefitApplication, User, UserDevice, UserSession, UserPushToken

KIND = "app_welcome"
FACE_VALUE = 1000
MOSCOW = ZoneInfo("Europe/Moscow")
START = datetime(2026, 11, 26, tzinfo=MOSCOW)


def no_pre_campaign_app_history(uid):
    # Legacy app sessions did not distinguish web / native clients. Do not
    # award a second "first visit" when a pre-campaign session is ambiguous.
    return (
        ~select(UserSession.id).where(UserSession.user_id == uid, UserSession.purpose == "app",
                                     UserSession.created_at < START).exists(),
        ~select(UserDevice.id).where(UserDevice.user_id == uid, UserDevice.platform.in_(("android", "ios")),
                                    UserDevice.first_seen_at < START).exists(),
        ~select(UserPushToken.id).where(UserPushToken.user_id == uid, UserPushToken.platform.in_(("android", "ios")),
                                       UserPushToken.created_at < START).exists(),
    )


def blocked_identity(email, counterparty):
    owner = aliased(User)
    same = func.lower(owner.email) == func.lower(email)
    if counterparty is not None:
        same = or_(same, owner.moysklad_counterparty_id == counterparty)
    prior_credit = select(LoyaltyBonusCredit.id).where(LoyaltyBonusCredit.user_id == owner.id,
        LoyaltyBonusCredit.source_kind.in_(("welcome", KIND))).exists()
    return select(owner.id).where(same, or_(owner.welcome_bonus_granted_at.is_not(None),
        prior_credit, ~and_(*no_pre_campaign_app_history(owner.id)))).exists()


async def grant_on_email_confirmation(db, user):
    if not user.email or user.welcome_bonus_granted_at is not None:
        return
    now = ufa_now()
    if now < START:
        return
    # Site and app normally share a user row. Also handle known duplicate
    # profiles without treating a name, household address or device as identity.
    email = user.email.strip().lower()
    keys = [f"welcome:email:{email}"]
    if user.moysklad_counterparty_id:
        keys.append(f"welcome:customer:{user.moysklad_counterparty_id}")
    for key in sorted(keys):
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))
    if await db.scalar(select(blocked_identity(email, user.moysklad_counterparty_id))):
        return
    # Share the historical key: never issue a second welcome credit at cutover.
    stmt = insert(LoyaltyBonusCredit).values(user_id=user.id, source_kind=KIND,
        idempotency_key=f"welcome:user:{user.id}", points=FACE_VALUE, status="local",
        earned_at=now, available_at=now, expires_at=now + timedelta(days=5))
    inserted = await db.scalar(stmt.on_conflict_do_nothing(index_elements=["idempotency_key"])
                               .returning(LoyaltyBonusCredit.id))
    if inserted is not None:
        user.welcome_bonus_granted_at = now
    return inserted


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
