from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.database.models import ReferralCommissionEntry, User
from .calculations import quantize_money, quantize_percent
from .commissions import current_previous_month_bounds, user_paid_order_total_for_period
from .ledger import get_deposit_balance
from .profile import get_or_create_referral_profile, referral_profile_total_purchases, refresh_profile_discount


async def get_referral_profile_summary(db: AsyncSession, *, user: User) -> dict[str, Any]:
    profile = await get_or_create_referral_profile(db, user=user)
    previous_start, current_start, next_month = current_previous_month_bounds(ufa_now())

    current_app_total = await user_paid_order_total_for_period(db, user_id=user.id, period_start=current_start, period_end=next_month)
    previous_app_total = await user_paid_order_total_for_period(db, user_id=user.id, period_start=previous_start, period_end=current_start)
    website_current = quantize_money(profile.current_month_purchase_total) if profile.website_seeded_at else Decimal("0.00")

    refresh_profile_discount(profile)
    accrued = quantize_money((await db.execute(select(func.coalesce(func.sum(ReferralCommissionEntry.commission_amount), 0)).where(ReferralCommissionEntry.referrer_user_id == user.id, ReferralCommissionEntry.status.in_(["posted", "pending"])))).scalar_one())

    return {
        "user_id": user.id,
        "total_purchases": referral_profile_total_purchases(profile),
        "initial_purchase_balance": quantize_money(profile.initial_purchase_balance),
        "website_seed_purchase_balance": quantize_money(profile.website_seed_purchase_balance),
        "app_paid_purchase_total": quantize_money(profile.app_paid_purchase_total),
        "current_month_purchases": quantize_money(website_current + current_app_total),
        "previous_month_purchases": previous_app_total,
        "current_discount_percent": quantize_percent(profile.current_discount_percent),
        "referrer_promo_code": profile.referrer_promo_code,
        "own_promo_code": profile.own_promo_code,
        "accrued_commissions": accrued,
        "deposit_balance": await get_deposit_balance(db, user.id),
        "website_seed_metadata": profile.website_seed_payload,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }