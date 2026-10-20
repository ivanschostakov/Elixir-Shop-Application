from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import BonusProgramPurchase, Order, ReferralProfile, User
from src.normalize import optional_str
from src.app.services.referrals.calculations import MIN_PERSONAL_DISCOUNT_SPEND, quantize_money
from src.app.services.referrals.profile import refresh_profile_discount
from src.app.services.referrals.program import ensure_default_reward_program, normalize_reward_program


async def _record_bonus_program_purchase(db: AsyncSession, *, order: Order, user: User, amount: Decimal, paid_at: datetime,) -> dict[str, Any]:
    await ensure_default_reward_program(db, user=user)
    profile = (await db.execute(select(ReferralProfile).where(ReferralProfile.user_id == user.id).with_for_update().execution_options(populate_existing=True))).scalar_one()
    if normalize_reward_program(profile.reward_program) != "bonus": return {"outcome": "program_changed"}

    snapshot = {
        "program": "bonus",
        "external_order_id": order.order_code or str(order.id),
        "amount": str(amount),
        "currency": order.currency,
        "paid_at": paid_at.isoformat(),
        "cashback_percent": 5,
        "bitrix_written": False,
    }
    statement = (insert(BonusProgramPurchase).values(order_id=order.id, user_id=user.id, external_order_id=order.order_code or str(order.id), amount=amount, currency=order.currency, paid_at=paid_at, status="posted", calculation_snapshot=snapshot,).on_conflict_do_nothing(index_elements=[BonusProgramPurchase.order_id]).returning(BonusProgramPurchase.id))
    purchase_id = (await db.execute(statement)).scalar_one_or_none()
    if purchase_id is None:
        await db.commit()
        return {"outcome": "already_recorded"}

    previous_total = quantize_money(profile.referral_discount_base_total)
    profile.referral_discount_base_total = quantize_money(previous_total + amount)
    refresh_profile_discount(profile, has_promo_code=bool(optional_str(user.promo_code)))
    await db.commit()
    return {
        "outcome": "recorded",
        "purchase_id": purchase_id,
        "purchase_total": str(profile.referral_discount_base_total),
        "selection_unlocked": (
            previous_total < MIN_PERSONAL_DISCOUNT_SPEND
            <= profile.referral_discount_base_total
        ),
    }


async def _reverse_bonus_program_purchase(db: AsyncSession, *, purchase: BonusProgramPurchase,) -> dict[str, Any]:
    if purchase.status == "reversed": return {"outcome": "already_reversed", "purchase_id": purchase.id}
    profile = (await db.execute(select(ReferralProfile).where(ReferralProfile.user_id == purchase.user_id).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if profile is not None:
        user = await db.get(User, purchase.user_id)
        profile.referral_discount_base_total = quantize_money(max(Decimal("0.00"), profile.referral_discount_base_total - purchase.amount,))
        refresh_profile_discount(
            profile,
            has_promo_code=bool(optional_str(user.promo_code)) if user else False,
        )
    purchase.status = "reversed"
    purchase.reversed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"outcome": "reversed", "purchase_id": purchase.id}
