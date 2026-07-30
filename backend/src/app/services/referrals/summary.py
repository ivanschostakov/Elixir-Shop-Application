import logging
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.app.services.benefits.moysklad_bonus import get_user_moysklad_bonus_wallet
from .calculations import quantize_money, quantize_percent
from .profile import get_or_create_referral_profile, referral_profile_total_purchases, refresh_profile_discount, user_has_promo_code
from .bitrix_sync import refresh_assigned_referrer_promo

logger = logging.getLogger(__name__)


async def get_referral_profile_summary(db: AsyncSession, *, user: User) -> dict[str, Any]:
    profile = await get_or_create_referral_profile(db, user=user)
    bonus_wallet = await get_user_moysklad_bonus_wallet(user)
    program_profile = await refresh_assigned_referrer_promo(db, user=user)
    if program_profile is not None:
        try:
            order_sum = program_profile.get("order_sum")
            if isinstance(order_sum, dict) and order_sum.get("amount") is not None:
                profile.referral_discount_base_total = quantize_money(
                    Decimal(str(order_sum["amount"]))
                )
            stored_percent = Decimal(str(program_profile.get("stored_discount_percent") or 0))
            group_percent = Decimal(str(program_profile.get("group_discount_percent") or 0))
            profile.current_discount_percent = quantize_percent(
                max(Decimal("3"), stored_percent, group_percent)
                if user_has_promo_code(user)
                else Decimal("0")
            )
        except (ValueError, TypeError):
            logger.exception("Could not apply Bitrix referral profile for user_id=%s", user.id)
            profile.referral_discount_base_total = bonus_wallet.sales_amount_rubles
            refresh_profile_discount(profile, has_promo_code=user_has_promo_code(user))
    else:
        profile.referral_discount_base_total = bonus_wallet.sales_amount_rubles
        refresh_profile_discount(profile, has_promo_code=user_has_promo_code(user))

    return {
        "user_id": user.id,
        "total_purchases": referral_profile_total_purchases(profile),
        "current_discount_percent": quantize_percent(profile.current_discount_percent),
        "promo_code": user.promo_code,
        "referral_discount_base_total": quantize_money(profile.referral_discount_base_total),
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "bonus_points": bonus_wallet.balance_points,
        "bonus_rubles": bonus_wallet.balance_rubles,
        "bonus_program_name": bonus_wallet.program_name,
        "bonus_spend_rate_points_to_ruble": bonus_wallet.spend_rate_points_to_ruble,
        "bonus_max_paid_rate_percent": bonus_wallet.max_paid_rate_percent,
    }
