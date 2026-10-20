from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import AppReferralPurchase, BonusProgramPurchase, ReferralProfile, User
from src.app.services.referrals.calculations import PARTNER_UNLOCK_SPEND, quantize_money
from src.app.services.referrals.profile import refresh_profile_discount
from src.app.services.referrals.program import ensure_default_reward_program, normalize_reward_program
from .common import logger


async def _increment_local_purchase_progress(db: AsyncSession, *, user: User, order_id: int, amount: Decimal, participates_in_program: bool,) -> None:
    if not participates_in_program: return
    legacy_purchase = (await db.execute(select(BonusProgramPurchase.id).where(BonusProgramPurchase.order_id == order_id, BonusProgramPurchase.status == "posted",))).scalar_one_or_none()
    if legacy_purchase is not None: return

    await ensure_default_reward_program(db, user=user)
    profile = (await db.execute(select(ReferralProfile).where(ReferralProfile.user_id == user.id).with_for_update().execution_options(populate_existing=True))).scalar_one()
    profile.referral_discount_base_total = quantize_money(profile.referral_discount_base_total + amount)
    refresh_profile_discount(profile, has_promo_code=True)
    if profile.referral_discount_base_total >= PARTNER_UNLOCK_SPEND: profile.partner_unlocked_at = (profile.partner_unlocked_at or datetime.now(timezone.utc))


async def _apply_remote_purchase_progress(db: AsyncSession, *, purchase: AppReferralPurchase, progress: dict[str, Any] | None,) -> None:
    if not isinstance(progress, dict) or purchase.buyer_user_id is None: return
    try:
        purchase_total = quantize_money(progress.get("new_total"))
        discount_percent = Decimal(str(progress.get("discount_percent") or 0))
    except (ArithmeticError, TypeError, ValueError):
        logger.warning(
            "Could not parse Bitrix purchase progress purchase_id=%s",
            purchase.id,
        )
        return

    profile = (await db.execute(select(ReferralProfile).where(ReferralProfile.user_id == purchase.buyer_user_id).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if profile is None: return
    profile.referral_discount_base_total = purchase_total
    if normalize_reward_program(profile.reward_program) == "bonus": refresh_profile_discount(profile, has_promo_code=bool(purchase.promo_code))
    else: profile.current_discount_percent = discount_percent
    profile.bitrix_sync_status = "synced"
    profile.bitrix_synced_at = datetime.now(timezone.utc)
    profile.bitrix_sync_error = None
    if purchase.bitrix_buyer_user_id: profile.bitrix_user_id = purchase.bitrix_buyer_user_id
    if purchase_total >= PARTNER_UNLOCK_SPEND: profile.partner_unlocked_at = (profile.partner_unlocked_at or datetime.now(timezone.utc))
