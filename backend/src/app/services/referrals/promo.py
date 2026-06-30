from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.database.models import ReferralProfile, User
from src.integrations.moysklad.client import MoySkladClient
from .profile import get_or_create_referral_profile, normalize_referral_code, refresh_profile_discount, refresh_profile_discount_from_moysklad


async def check_referrer_code(db: AsyncSession, *, user: User, code: str) -> dict[str, Any]:
    normalized_code = normalize_referral_code(code)
    return {
        "code": normalized_code,
        "is_valid": False,
        "status": "not_configured" if normalized_code else "empty",
        "reason": "Promo code validation is not configured" if normalized_code else "Promo code is required",
        "warning": None,
        "requires_confirmation": False,
        "referrer_user_id": None,
        "depth": None,
    }


async def attach_referrer_code(
    db: AsyncSession,
    *,
    user: User,
    code: str,
    confirmed: bool = False,
    moysklad_client: MoySkladClient | None = None,
) -> ReferralProfile:
    check = await check_referrer_code(db, user=user, code=code)
    if not check["is_valid"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=check["reason"] or "Invalid promo code")
    if check["requires_confirmation"] and not confirmed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=check["warning"])

    normalized_code = check["code"]
    profile = await get_or_create_referral_profile(db, user=user)
    user.promo_code = normalized_code
    await refresh_profile_discount_from_moysklad(profile, user=user, moysklad_client=moysklad_client)
    await db.flush()
    return profile


async def detach_referrer_code(db: AsyncSession, *, user: User) -> ReferralProfile:
    profile = await get_or_create_referral_profile(db, user=user)
    user.promo_code = None
    refresh_profile_discount(profile, has_promo_code=False)
    await db.flush()
    return profile
