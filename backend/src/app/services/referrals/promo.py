from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.database.models import ReferralProfile, User
from src.integrations.bitrix_promo import (
    BitrixPromoClient,
    BitrixPromoError,
    bitrix_promo_configured,
)
from src.integrations.moysklad.client import MoySkladClient
from .profile import get_or_create_referral_profile, normalize_referral_code, refresh_profile_discount
from .program import normalize_reward_program


async def _require_partner_program(db: AsyncSession, *, user: User) -> ReferralProfile:
    profile = await get_or_create_referral_profile(db, user=user)
    if normalize_reward_program(profile.reward_program) != "partner":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Промокоды доступны только в партнёрской программе / Promo codes are available only in the partner program",
        )
    return profile


async def check_referrer_code(db: AsyncSession, *, user: User, code: str) -> dict[str, Any]:
    await _require_partner_program(db, user=user)
    normalized_code = normalize_referral_code(code)
    if normalized_code and bitrix_promo_configured():
        try:
            promo = await BitrixPromoClient().lookup(normalized_code)
        except BitrixPromoError as error:
            if error.status_code == status.HTTP_404_NOT_FOUND:
                return {
                    "code": normalized_code,
                    "is_valid": False,
                    "status": "not_found",
                    "reason": error.message_ru,
                    "warning": None,
                    "requires_confirmation": False,
                    "referrer_user_id": None,
                    "depth": None,
                }
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Проверка промокода временно недоступна / Promo validation is temporarily unavailable",
            ) from error

        return {
            "code": str(promo.get("promo") or normalized_code),
            "is_valid": True,
            "status": "active",
            "reason": None,
            "warning": None,
            "requires_confirmation": False,
            "referrer_user_id": None,
            "depth": None,
        }

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
    profile = await _require_partner_program(db, user=user)
    check = await check_referrer_code(db, user=user, code=code)
    if not check["is_valid"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=check["reason"] or "Invalid promo code")
    if check["requires_confirmation"] and not confirmed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=check["warning"])

    normalized_code = check["code"]
    if bitrix_promo_configured():
        try:
            remote_result = await BitrixPromoClient().attach_referrer(
                promo=normalized_code,
                user_email=user.email,
            )
        except BitrixPromoError as error:
            if error.code in {"own_promo_not_allowed", "referral_cycle_not_allowed"}:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"{error.message_ru} / {error.message_en}",
                ) from error
            if error.code == "user_not_found":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Профиль покупателя на сайте не найден / Website customer profile was not found",
                ) from error
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось сохранить промокод на сайте / Could not save the promo code on the website",
            ) from error
    else:
        remote_result = None

    user.promo_code = normalized_code
    if remote_result is not None and remote_result.get("progress_reset"):
        profile.referral_discount_base_total = 0
        profile.current_discount_percent = 0
    await db.flush()
    return profile


async def detach_referrer_code(db: AsyncSession, *, user: User) -> ReferralProfile:
    profile = await _require_partner_program(db, user=user)
    if bitrix_promo_configured():
        try:
            await BitrixPromoClient().detach_referrer(user_email=user.email)
        except BitrixPromoError as error:
            if error.code != "user_not_found":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Не удалось отвязать промокод на сайте / Could not unlink the promo code on the website",
                ) from error
    user.promo_code = None
    profile.referral_discount_base_total = 0
    refresh_profile_discount(profile, has_promo_code=False)
    await db.flush()
    return profile
