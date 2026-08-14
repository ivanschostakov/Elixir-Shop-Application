from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal, cast

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.database.models import ReferralProfile, RewardProgramSelectionEvent, User
from src.integrations.bitrix_promo import (
    BitrixPromoClient,
    BitrixPromoError,
    bitrix_promo_configured,
)
from src.normalize import optional_str

from .calculations import MIN_PERSONAL_DISCOUNT_SPEND, quantize_money, quantize_percent
from .profile import get_or_create_referral_profile, refresh_profile_discount

RewardProgram = Literal["bonus", "partner"]
DEFAULT_REWARD_PROGRAM: RewardProgram = "bonus"
REWARD_PROGRAMS = frozenset(("bonus", "partner"))
LEGACY_REWARD_PROGRAMS = frozenset(("combined",))
LOCKED_REWARD_PROGRAM_SOURCES = frozenset(("user", "admin"))


def normalize_reward_program(value: str | None) -> RewardProgram | None:
    normalized = optional_str(value)
    if normalized not in REWARD_PROGRAMS:
        return None
    return cast(RewardProgram, normalized)


def reward_program_selection_available(profile: ReferralProfile) -> bool:
    return quantize_money(profile.referral_discount_base_total) >= MIN_PERSONAL_DISCOUNT_SPEND


def reward_program_selection_required(profile: ReferralProfile) -> bool:
    return (
        reward_program_selection_available(profile)
        and profile.reward_program_selection_source not in LOCKED_REWARD_PROGRAM_SOURCES
    )


async def ensure_default_reward_program(
    db: AsyncSession,
    *,
    user: User,
) -> ReferralProfile:
    """Default to bonuses while keeping an assigned promo active at the base 3%."""
    profile = await get_or_create_referral_profile(db, user=user)
    existing_promo = optional_str(user.promo_code)
    if normalize_reward_program(profile.reward_program) is None:
        previous_value = optional_str(profile.reward_program)
        profile.reward_program = DEFAULT_REWARD_PROGRAM
        profile.reward_program_selected_at = None
        profile.reward_program_selection_source = "system_default"
        snapshot = dict(profile.reward_program_snapshot or {})
        if previous_value in LEGACY_REWARD_PROGRAMS:
            snapshot["migrated_from"] = previous_value
        if existing_promo:
            snapshot.pop("deferred_existing_promo", None)
            snapshot["active_base_promo"] = existing_promo
        profile.reward_program_snapshot = snapshot
    elif profile.reward_program_selection_source == "system_existing_promo":
        # A previous migration incorrectly treated the mere presence of a
        # website promo as the customer's one-time program choice. Restore the
        # approved default while retaining the website relationship for later.
        profile.reward_program = DEFAULT_REWARD_PROGRAM
        profile.reward_program_selected_at = None
        profile.reward_program_selection_source = "system_default"
        snapshot = dict(profile.reward_program_snapshot or {})
        snapshot.pop("recovered_existing_promo", None)
        if existing_promo:
            snapshot.pop("deferred_existing_promo", None)
            snapshot["active_base_promo"] = existing_promo
        profile.reward_program_snapshot = snapshot
    elif (
        profile.reward_program == DEFAULT_REWARD_PROGRAM
        and profile.reward_program_selection_source == "system_default"
        and existing_promo
    ):
        snapshot = dict(profile.reward_program_snapshot or {})
        if snapshot.get("active_base_promo") != existing_promo:
            snapshot.pop("deferred_existing_promo", None)
            snapshot["active_base_promo"] = existing_promo
            profile.reward_program_snapshot = snapshot
    if normalize_reward_program(profile.reward_program) == DEFAULT_REWARD_PROGRAM:
        refresh_profile_discount(profile, has_promo_code=bool(existing_promo))
    await db.flush()
    return profile


def _money_from_program_profile(program_profile: dict[str, Any]) -> Decimal:
    order_sum = program_profile.get("order_sum")
    if not isinstance(order_sum, dict) or order_sum.get("amount") is None:
        return Decimal("0.00")
    try:
        return quantize_money(order_sum["amount"])
    except (ArithmeticError, TypeError, ValueError):
        return Decimal("0.00")


async def _load_bitrix_program_profile(user: User) -> dict[str, Any] | None:
    if not bitrix_promo_configured() or not user.email:
        return None
    try:
        response = await BitrixPromoClient().profile(user_email=user.email)
    except BitrixPromoError as error:
        if error.code == "user_not_found":
            return None
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Профиль программы на сайте временно недоступен / Website program profile is temporarily unavailable",
        ) from error
    except (RuntimeError, httpx.HTTPError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Профиль программы на сайте временно недоступен / Website program profile is temporarily unavailable",
        ) from error

    program_profile = response.get("program_profile")
    if not isinstance(program_profile, dict):
        return None
    bitrix_user_id = response.get("user_id") or program_profile.get("user_id")
    if bitrix_user_id:
        program_profile = dict(program_profile)
        program_profile["user_id"] = int(bitrix_user_id)
    return program_profile


async def select_reward_program(
    db: AsyncSession,
    *,
    user: User,
    program: str,
    source: str = "user",
    force: bool = False,
    reason: str | None = None,
    selected_by_admin_user_id: int | None = None,
) -> ReferralProfile:
    normalized_program = normalize_reward_program(program)
    if normalized_program is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Выберите накопительную или реферальную программу / Choose the cumulative or referral program",
        )

    profile = await ensure_default_reward_program(db, user=user)
    previous_program = normalize_reward_program(profile.reward_program)
    explicit_selection = profile.reward_program_selection_source in LOCKED_REWARD_PROGRAM_SOURCES
    if not force and not reward_program_selection_available(profile):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Выбор программы станет доступен после 30 000 ₽ личных покупок / Program selection becomes available after 30,000 RUB of personal purchases",
        )
    if previous_program == normalized_program and explicit_selection:
        return profile
    if explicit_selection and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Программа уже выбрана. Для изменения обратитесь к администратору / The program is already selected. Contact an administrator to change it",
        )

    bitrix_profile_error: str | None = None
    try:
        bitrix_profile = await _load_bitrix_program_profile(user)
    except HTTPException as error:
        if normalized_program == "partner":
            raise
        bitrix_profile = None
        bitrix_profile_error = str(error.detail)

    selected_at = datetime.now(timezone.utc)
    snapshot: dict[str, Any] = {
        "selected_at": selected_at.isoformat(),
        "source": source,
        "previous_program": previous_program,
        "bitrix_profile_found": bitrix_profile is not None,
        "personal_purchase_total": str(quantize_money(profile.referral_discount_base_total)),
    }
    if bitrix_profile_error:
        snapshot["bitrix_opening_import_error"] = bitrix_profile_error
    if bitrix_profile is not None:
        bitrix_user_id = int(bitrix_profile.get("user_id") or 0)
        if bitrix_user_id > 0:
            profile.bitrix_user_id = bitrix_user_id
        opening_balance = _money_from_program_profile(bitrix_profile)
        snapshot["bitrix_opening_balance"] = str(opening_balance)
        profile.referral_discount_base_total = max(
            quantize_money(profile.referral_discount_base_total),
            opening_balance,
        )
        if normalized_program == "partner":
            if profile.referral_discount_base_total > opening_balance:
                try:
                    synced_balance = await BitrixPromoClient().set_opening_balance(
                        amount=str(profile.referral_discount_base_total),
                        bitrix_user_id=bitrix_user_id or None,
                        user_email=user.email,
                    )
                except (BitrixPromoError, RuntimeError, httpx.HTTPError) as error:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Не удалось перенести сумму покупок в реферальную программу / Could not import the purchase total into the referral program",
                    ) from error
                snapshot["bitrix_imported_purchase_total"] = str(
                    quantize_money(synced_balance.get("new_total"))
                )
            stored_percent = Decimal(str(bitrix_profile.get("stored_discount_percent") or 0))
            group_percent = Decimal(str(bitrix_profile.get("group_discount_percent") or 0))
            profile.current_discount_percent = quantize_percent(
                max(Decimal("0"), stored_percent, group_percent)
            )
            user.promo_code = optional_str(bitrix_profile.get("referrer_promo"))

    profile.reward_program = normalized_program
    if normalized_program == "bonus":
        active_promo = optional_str(user.promo_code)
        if bitrix_profile is not None:
            active_promo = optional_str(bitrix_profile.get("referrer_promo")) or active_promo
        if active_promo:
            snapshot["active_base_promo"] = active_promo
        refresh_profile_discount(profile, has_promo_code=bool(active_promo))
    else:
        # Once the partner path is selected, the same assigned promo starts
        # using the accumulated purchase total instead of the fixed base 3%.
        remote_discount_percent = profile.current_discount_percent
        refresh_profile_discount(
            profile,
            has_promo_code=bool(optional_str(user.promo_code)),
        )
        if bitrix_profile is not None and optional_str(user.promo_code):
            profile.current_discount_percent = quantize_percent(
                max(profile.current_discount_percent, remote_discount_percent)
            )

    profile.reward_program_selected_at = selected_at
    profile.reward_program_selection_source = source
    profile.reward_program_snapshot = snapshot
    db.add(
        RewardProgramSelectionEvent(
            user_id=user.id,
            previous_program=previous_program,
            selected_program=normalized_program,
            source=source,
            reason=optional_str(reason),
            selected_by_admin_user_id=selected_by_admin_user_id,
            snapshot=snapshot,
        )
    )
    await db.flush()
    return profile
