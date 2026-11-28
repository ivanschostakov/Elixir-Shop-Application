from typing import Any

from fastapi import HTTPException
from config import LOYALTY_USE_SETTLEMENT_BALANCE
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.database.models import ReferralProfile, User
from src.integrations.bitrix_promo import (
    BitrixPromoClient,
    BitrixPromoError,
    bitrix_promo_configured,
)
from src.integrations.moysklad.client import MoySkladClient
from src.normalize import ms_referrer_code
from .bitrix_sync import refresh_program_profile_from_bitrix
from .profile import normalize_referral_code, refresh_profile_discount
from .program import ensure_default_reward_program, moysklad_program_is_authoritative


async def _get_program_profile(db: AsyncSession, *, user: User) -> ReferralProfile:
    return await ensure_default_reward_program(db, user=user)


async def check_referrer_code(db: AsyncSession, *, user: User, code: str) -> dict[str, Any]:
    profile = await _get_program_profile(db, user=user)
    normalized_code = normalize_referral_code(code)
    current_code = normalize_referral_code(user.promo_code)
    accounting_buyer = LOYALTY_USE_SETTLEMENT_BALANCE and getattr(user, "moysklad_counterparty_id", None)
    if normalized_code and (accounting_buyer or moysklad_program_is_authoritative(profile)) and (not current_code or normalized_code == current_code):
        from .ms_codes import resolve_ms_referrer
        try:
            owner = await resolve_ms_referrer(normalized_code, buyer_id=user.moysklad_counterparty_id)
        except HTTPException as exc:
            if exc.status_code != 422:
                raise
            return {"code": normalized_code, "is_valid": False, "status": "not_found",
                    "reason": exc.detail, "warning": None, "requires_confirmation": False,
                    "referrer_user_id": None, "depth": None}
        return {"code": owner.code, "is_valid": True, "status": "already_attached" if current_code else "active",
                "reason": None, "warning": None, "requires_confirmation": False, "referrer_user_id": None, "depth": None}
    if current_code and normalized_code and normalized_code != current_code:
        return {
            "code": normalized_code,
            "is_valid": False,
            "status": "detach_required",
            "reason": (
                "Сначала отвяжите текущий промокод, затем введите новый / "
                "Unlink the current promo code before entering a new one"
            ),
            "warning": None,
            "requires_confirmation": False,
            "referrer_user_id": None,
            "depth": None,
        }
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

        canonical = ms_referrer_code(promo.get("promo"))
        if normalize_referral_code(canonical) != normalized_code:
            raise HTTPException(503, "Сервис не подтвердил введённый промокод. Попробуйте позже.")
        return {
            "code": canonical,
            "is_valid": True,
            "status": "already_attached" if current_code else "active",
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
    profile = await _get_program_profile(db, user=user)
    if getattr(profile, "reward_program_selection_source", None) == "registration":
        raise HTTPException(409, "Сначала выберите программу после регистрации.")
    normalized_requested_code = normalize_referral_code(code)
    current_code = normalize_referral_code(user.promo_code)
    if not normalized_requested_code:
        raise HTTPException(422, "Введите действующий промокод.")
    if current_code == normalized_requested_code:
        check = await check_referrer_code(db, user=user, code=code)
        if not check["is_valid"]:
            raise HTTPException(422, check["reason"] or "Промокод не найден.")
        return profile
    if moysklad_program_is_authoritative(profile) or (LOYALTY_USE_SETTLEMENT_BALANCE and getattr(user, "moysklad_counterparty_id", None)):
        if not current_code:
            raise HTTPException(409, "Введите промокод в корзине. Он будет закреплён при оформлении заказа.")
        raise HTTPException(409, "Программа уже определена в МойСкладе. Для изменения обратитесь в поддержку.")
    if current_code:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Сначала отвяжите текущий промокод, затем введите новый / "
                "Unlink the current promo code before entering a new one"
            ),
        )
    check = await check_referrer_code(db, user=user, code=code)
    if not check["is_valid"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=check["reason"] or "Invalid promo code")
    if check["requires_confirmation"] and not confirmed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=check["warning"])

    normalized_code = check["code"]
    if bitrix_promo_configured():
        client = BitrixPromoClient()
        try:
            remote_result = await client.attach_referrer(
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
        outcome = str(remote_result.get("outcome") or "")
        if outcome == "sale_coupon":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Обычный скидочный купон применяется в корзине и не закрепляется за профилем / "
                    "A regular discount coupon is applied in the cart and is not assigned to the profile"
                ),
            )
    else:
        remote_result = None

    user.promo_code = normalized_code
    # Purchases made in the 5% cashback program do not grow the referral
    # discount. A newly assigned relationship starts from the base 3% tier.
    profile.referral_discount_base_total = 0
    profile = await ensure_default_reward_program(db, user=user)
    if remote_result is not None:
        await refresh_program_profile_from_bitrix(db, user=user)
    else:
        refresh_profile_discount(profile, has_promo_code=True)
    await db.flush()
    return profile


async def detach_referrer_code(db: AsyncSession, *, user: User) -> ReferralProfile:
    if LOYALTY_USE_SETTLEMENT_BALANCE and getattr(user, "moysklad_counterparty_id", None):
        raise HTTPException(409, "Подтвердите отвязку промокода в личном кабинете.")
    profile = await _get_program_profile(db, user=user)
    if getattr(profile, "reward_program_selection_source", None) == "registration":
        raise HTTPException(409, "Сначала выберите программу после регистрации.")
    if moysklad_program_is_authoritative(profile):
        raise HTTPException(409, "Программа уже определена в МойСкладе. Для изменения обратитесь в поддержку.")
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
    profile = await ensure_default_reward_program(db, user=user)
    profile.referral_discount_base_total = 0
    refresh_profile_discount(profile, has_promo_code=False)
    if bitrix_promo_configured():
        await refresh_program_profile_from_bitrix(db, user=user)
    await db.flush()
    return profile
