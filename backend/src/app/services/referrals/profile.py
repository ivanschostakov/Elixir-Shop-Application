from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.database.models import ReferralProfile, User
from src.normalize import optional_str
from .calculations import calculate_personal_discount_percent, quantize_money, quantize_percent

MAX_REFERRAL_TREE_LEVEL = 3


def normalize_referral_code(code: str | None) -> str | None:
    code = optional_str(code)
    return code.upper() if code else None


def referral_profile_total_purchases(profile: ReferralProfile) -> Decimal:
    return quantize_money(profile.initial_purchase_balance) + quantize_money(profile.website_seed_purchase_balance) + quantize_money(profile.app_paid_purchase_total)


def discount_base_from_percent(value: Decimal | int | float | str | None) -> Decimal:
    percent = quantize_percent(value)
    if percent >= Decimal("20.00"): return Decimal("200000.00")
    if percent >= Decimal("4.00"): return quantize_money(percent * Decimal("10000.00"))
    return Decimal("0.00")


def website_seed_referral_payload(profile: ReferralProfile) -> dict[str, Any]:
    seed = profile.website_seed_payload if isinstance(profile.website_seed_payload, dict) else {}
    payload = seed.get("referral_profile")
    return payload if isinstance(payload, dict) else {}


def website_seed_referral_percent(profile: ReferralProfile) -> Decimal:
    return quantize_percent(website_seed_referral_payload(profile).get("referral_percent"))


def profile_has_referral_participation(profile: ReferralProfile) -> bool:
    return bool(profile.referrer_promo_code) or website_seed_referral_percent(profile) > Decimal("0.00")


def refresh_profile_discount(profile: ReferralProfile) -> None:
    profile.current_discount_percent = calculate_personal_discount_percent(profile.referral_discount_base_total, has_referrer=profile_has_referral_participation(profile))


def website_discount_base_from_referral_data(data: dict[str, Any] | None) -> Decimal:
    if data is None: return Decimal("0.00")
    return max(quantize_money(data.get("referral_turnover_amount")), discount_base_from_percent(data.get("referral_percent")))


def sync_website_referral_discount_base(profile: ReferralProfile, *, old_website_base: Decimal, new_website_base: Decimal, is_first_website_seed: bool, website_participates: bool) -> None:
    if not website_participates and not profile.referrer_promo_code:
        profile.referral_discount_base_total = Decimal("0.00")
        refresh_profile_discount(profile)
        return

    current = quantize_money(profile.referral_discount_base_total)
    if is_first_website_seed: profile.referral_discount_base_total = current + new_website_base if current > Decimal("0.00") else quantize_money(profile.initial_purchase_balance) + quantize_money(profile.app_paid_purchase_total) + new_website_base
    else: profile.referral_discount_base_total = max(Decimal("0.00"), current - old_website_base) + new_website_base
    refresh_profile_discount(profile)


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