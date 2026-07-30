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

from .calculations import quantize_money, quantize_percent
from .profile import get_or_create_referral_profile, refresh_profile_discount

RewardProgram = Literal["bonus", "partner"]
REWARD_PROGRAMS = frozenset(("bonus", "partner"))


def normalize_reward_program(value: str | None) -> RewardProgram | None:
    normalized = optional_str(value)
    if normalized not in REWARD_PROGRAMS:
        return None
    return cast(RewardProgram, normalized)


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
    program: RewardProgram,
    source: str = "user",
    force: bool = False,
    reason: str | None = None,
    selected_by_admin_user_id: int | None = None,
) -> ReferralProfile:
    normalized_program = normalize_reward_program(program)
    if normalized_program is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Выберите бонусную или партнёрскую программу / Choose the bonus or partner program",
        )

    profile = await get_or_create_referral_profile(db, user=user)
    previous_program = normalize_reward_program(profile.reward_program)
    if previous_program == normalized_program:
        return profile
    if previous_program is not None and not force:
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
    if normalized_program == "partner" and bitrix_profile is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Для партнёрской программы нужен активный профиль на сайте / An active website profile is required for the partner program",
        )

    selected_at = datetime.now(timezone.utc)
    snapshot: dict[str, Any] = {
        "selected_at": selected_at.isoformat(),
        "source": source,
        "previous_program": previous_program,
        "bitrix_profile_found": bitrix_profile is not None,
    }
    if bitrix_profile_error:
        snapshot["bitrix_opening_import_error"] = bitrix_profile_error
    if bitrix_profile is not None:
        bitrix_user_id = int(bitrix_profile.get("user_id") or 0)
        if bitrix_user_id > 0:
            profile.bitrix_user_id = bitrix_user_id
        opening_balance = _money_from_program_profile(bitrix_profile)
        snapshot["bitrix_opening_balance"] = str(opening_balance)
        snapshot["bitrix_opening_cutoff"] = selected_at.isoformat()
        if normalized_program == "bonus":
            profile.referral_discount_base_total = max(
                quantize_money(profile.referral_discount_base_total),
                opening_balance,
            )
        else:
            profile.referral_discount_base_total = opening_balance
            stored_percent = Decimal(str(bitrix_profile.get("stored_discount_percent") or 0))
            group_percent = Decimal(str(bitrix_profile.get("group_discount_percent") or 0))
            profile.current_discount_percent = quantize_percent(
                max(Decimal("0"), stored_percent, group_percent)
            )
            user.promo_code = optional_str(bitrix_profile.get("referrer_promo"))

    if normalized_program == "bonus":
        user.promo_code = None
        refresh_profile_discount(profile)

    profile.reward_program = normalized_program
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
