import logging
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.integrations.bitrix_promo import BitrixPromoClient, BitrixPromoError, bitrix_promo_configured
from .calculations import quantize_money, quantize_percent
from .profile import get_or_create_referral_profile, referral_profile_total_purchases, refresh_profile_discount_from_moysklad

logger = logging.getLogger(__name__)


async def get_referral_profile_summary(db: AsyncSession, *, user: User) -> dict[str, Any]:
    profile = await get_or_create_referral_profile(db, user=user)
    if bitrix_promo_configured() and user.promo_code:
        try:
            context = await BitrixPromoClient().context(
                promo=user.promo_code,
                user_email=user.email,
            )
            program_profile = context.get("program_profile")
            order_sum = program_profile.get("order_sum") if isinstance(program_profile, dict) else None
            if isinstance(order_sum, dict) and order_sum.get("amount") is not None:
                profile.referral_discount_base_total = quantize_money(
                    Decimal(str(order_sum["amount"]))
                )
            profile.current_discount_percent = quantize_percent(
                Decimal(str(context.get("display_discount_percent") or 0))
            )
        except (BitrixPromoError, ValueError, TypeError):
            logger.exception("Could not refresh Bitrix referral context for user_id=%s", user.id)
            await refresh_profile_discount_from_moysklad(profile, user=user)
    else:
        await refresh_profile_discount_from_moysklad(profile, user=user)

    return {
        "user_id": user.id,
        "total_purchases": referral_profile_total_purchases(profile),
        "current_discount_percent": quantize_percent(profile.current_discount_percent),
        "promo_code": user.promo_code,
        "referral_discount_base_total": quantize_money(profile.referral_discount_base_total),
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }
