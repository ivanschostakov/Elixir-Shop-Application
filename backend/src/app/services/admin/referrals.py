from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select
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


async def referral_summary(db: AsyncSession) -> dict[str, Any]:
    totals = (await db.execute(select(
        func.count(ReferralProfile.id),
        func.coalesce(func.sum(ReferralProfile.referral_discount_base_total), 0),
        func.coalesce(func.avg(ReferralProfile.current_discount_percent), 0),
        func.coalesce(func.max(ReferralProfile.current_discount_percent), 0),
        func.coalesce(func.sum(case((ReferralProfile.referral_discount_base_total > 0, 1), else_=0)), 0),
    ))).one()
    band_rows = (await db.execute(select(
        case(
            (ReferralProfile.current_discount_percent <= 0, "0%"),
            (ReferralProfile.current_discount_percent < 5, "1–4%"),
            (ReferralProfile.current_discount_percent < 10, "5–9%"),
            else_="10%+",
        ).label("band"),
        func.count(ReferralProfile.id),
    ).group_by("band"))).all()
    return {
        "profiles_count": int(totals[0] or 0),
        "total_discount_base": quantize_money(totals[1] or 0),
        "average_discount_percent": totals[2] or 0,
        "max_discount_percent": totals[3] or 0,
        "active_referrers_count": int(totals[4] or 0),
        "discount_bands": [{"band": str(band), "count": int(count)} for band, count in band_rows],
    }
