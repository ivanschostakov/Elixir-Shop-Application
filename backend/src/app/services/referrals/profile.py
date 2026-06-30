import logging
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.database.models import ReferralProfile, User
from src.integrations.moysklad.client import MoySkladClient, get_moysklad_client
from src.normalize import optional_str
from .calculations import calculate_personal_discount_percent, quantize_money

MOYSKLAD_MONEY_MINOR_UNITS = Decimal("100.00")
logger = logging.getLogger(__name__)


def normalize_referral_code(code: str | None) -> str | None:
    code = optional_str(code)
    return code.upper() if code else None


def referral_profile_total_purchases(profile: ReferralProfile) -> Decimal:
    return quantize_money(profile.referral_discount_base_total)


def user_has_promo_code(user: User) -> bool:
    return bool(normalize_referral_code(user.promo_code))


def refresh_profile_discount(profile: ReferralProfile, *, has_promo_code: bool | None = None) -> None:
    profile.current_discount_percent = calculate_personal_discount_percent(
        profile.referral_discount_base_total,
        has_promo_code=bool(has_promo_code),
    )


def moysklad_counterparty_sales_amount_rubles(counterparty: dict[str, Any] | None) -> Decimal:
    if not isinstance(counterparty, dict):
        return Decimal("0.00")

    raw_sales_amount = counterparty.get("salesAmount")
    if raw_sales_amount is None:
        return Decimal("0.00")

    try:
        return quantize_money(Decimal(str(raw_sales_amount)) / MOYSKLAD_MONEY_MINOR_UNITS)
    except Exception:
        logger.warning("Could not parse MoySklad counterparty salesAmount=%r", raw_sales_amount)
        return Decimal("0.00")


async def refresh_profile_discount_from_moysklad(
    profile: ReferralProfile,
    *,
    user: User,
    moysklad_client: MoySkladClient | None = None,
) -> None:
    profile.referral_discount_base_total = Decimal("0.00")

    client = moysklad_client or get_moysklad_client()
    if user.moysklad_counterparty_id is not None and client.is_configured():
        try:
            counterparty = await client.get_counterparty(user.moysklad_counterparty_id)
            profile.referral_discount_base_total = moysklad_counterparty_sales_amount_rubles(counterparty)
        except Exception:
            logger.exception("Could not refresh referral discount base from MoySklad user_id=%s counterparty_id=%s", user.id, user.moysklad_counterparty_id)

    refresh_profile_discount(profile, has_promo_code=user_has_promo_code(user))


async def get_referral_profile_by_user_id(db: AsyncSession, user_id: int) -> ReferralProfile | None:
    return (await db.execute(select(ReferralProfile).where(ReferralProfile.user_id == user_id))).scalar_one_or_none()


def is_referral_profile_user_unique_violation(error: IntegrityError) -> bool:
    direct = getattr(getattr(error, "orig", None), "constraint_name", None)
    diag = getattr(getattr(getattr(error, "orig", None), "diag", None), "constraint_name", None)
    return "referral_profiles_user_id_key" in {direct, diag, str(error)}


async def get_or_create_referral_profile(db: AsyncSession, *, user: User | None = None, user_id: int | None = None) -> ReferralProfile:
    user_id = user.id if user is not None else user_id
    if user_id is None: raise ValueError("user or user_id is required")

    with db.no_autoflush: profile = await get_referral_profile_by_user_id(db, user_id)
    if profile: return profile

    stmt = insert(ReferralProfile).values(user_id=user_id, current_discount_percent=Decimal("0.00")).on_conflict_do_nothing(index_elements=[ReferralProfile.user_id]).returning(ReferralProfile.id)

    try:
        async with db.begin_nested(): profile_id = (await db.execute(stmt)).scalar_one_or_none()
    except IntegrityError as exc:
        if not is_referral_profile_user_unique_violation(exc): raise
        profile_id = None

    profile = await db.get(ReferralProfile, profile_id) if profile_id else await get_referral_profile_by_user_id(db, user_id)
    if profile is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create referral profile")
    return profile
