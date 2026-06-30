from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services.referrals.calculations import quantize_money
from src.database.crud.referrals import list_referral_profiles as list_referral_profile_rows
from src.database.models import ReferralProfile


def _profile_row(profile: ReferralProfile) -> dict[str, Any]:
    total = quantize_money(profile.referral_discount_base_total)
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "total_purchases": total,
        "referral_discount_base_total": total,
        "current_discount_percent": profile.current_discount_percent,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


async def list_profiles(db: AsyncSession, *, limit: int, offset: int) -> list[dict[str, Any]]:
    profiles = await list_referral_profile_rows(db, limit=limit, offset=offset)
    return [_profile_row(profile) for profile in profiles]
