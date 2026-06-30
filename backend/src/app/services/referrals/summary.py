from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from .calculations import quantize_money, quantize_percent
from .profile import get_or_create_referral_profile, referral_profile_total_purchases, refresh_profile_discount_from_moysklad


async def get_referral_profile_summary(db: AsyncSession, *, user: User) -> dict[str, Any]:
    profile = await get_or_create_referral_profile(db, user=user)
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
