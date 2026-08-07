import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ReferralProfile, User
from src.integrations.bitrix_promo import (
    BitrixPromoClient,
    BitrixPromoError,
    bitrix_promo_configured,
)
from src.normalize import optional_str

from .calculations import PARTNER_UNLOCK_SPEND, quantize_money, quantize_percent
from .program import ensure_default_reward_program

logger = logging.getLogger(__name__)


def _program_profile(response: dict[str, Any]) -> dict[str, Any] | None:
    value = response.get("program_profile")
    return value if isinstance(value, dict) else None


def _remote_purchase_total(program_profile: dict[str, Any]) -> Decimal:
    order_sum = program_profile.get("order_sum")
    if not isinstance(order_sum, dict):
        return Decimal("0.00")
    try:
        return quantize_money(order_sum.get("amount"))
    except (ArithmeticError, TypeError, ValueError):
        return Decimal("0.00")


def apply_bitrix_program_profile(
    profile: ReferralProfile,
    *,
    user: User,
    program_profile: dict[str, Any],
    bitrix_user_id: int | None = None,
) -> None:
    remote_purchase_total = _remote_purchase_total(program_profile)
    stored_percent = Decimal(str(program_profile.get("stored_discount_percent") or 0))
    group_percent = Decimal(str(program_profile.get("group_discount_percent") or 0))
    discount_percent = quantize_percent(
        max(Decimal("0"), stored_percent, group_percent)
    )
    own_promo = optional_str(program_profile.get("own_promo"))
    referrer_promo = optional_str(program_profile.get("referrer_promo"))
    firm_promo_codes = program_profile.get("firm_promo_codes")
    normalized_firm_promo_codes = {
        code.casefold()
        for code in (
            optional_str(value)
            for value in (
                firm_promo_codes if isinstance(firm_promo_codes, list) else []
            )
        )
        if code
    }
    current_local_promo = optional_str(user.promo_code)
    effective_promo = referrer_promo
    if (
        effective_promo is None
        and current_local_promo
        and current_local_promo.casefold() in normalized_firm_promo_codes
    ):
        effective_promo = current_local_promo
    purchase_total = (
        remote_purchase_total if effective_promo is not None else Decimal("0.00")
    )
    effective_discount_percent = (
        quantize_percent(max(Decimal("3.00"), discount_percent))
        if effective_promo is not None
        else Decimal("0.00")
    )
    now = datetime.now(timezone.utc)

    if bitrix_user_id and bitrix_user_id > 0:
        profile.bitrix_user_id = bitrix_user_id
    profile.referral_discount_base_total = purchase_total
    profile.current_discount_percent = effective_discount_percent
    profile.bitrix_sync_status = "synced"
    profile.bitrix_synced_at = now
    profile.bitrix_sync_error = None
    if own_promo or purchase_total >= PARTNER_UNLOCK_SPEND:
        profile.partner_unlocked_at = profile.partner_unlocked_at or now
    user.promo_code = effective_promo

    snapshot = dict(profile.reward_program_snapshot or {})
    snapshot.update(
        {
            "mode": "partner",
            "bitrix_user_id": profile.bitrix_user_id,
            "bitrix_purchase_total": str(remote_purchase_total),
            "participating_purchase_total": str(purchase_total),
            "bitrix_discount_percent": str(discount_percent),
            "effective_discount_percent": str(effective_discount_percent),
            "bitrix_own_promo": own_promo,
            "bitrix_referrer_promo": referrer_promo,
            "effective_app_promo": effective_promo,
            "bitrix_synced_at": now.isoformat(),
        }
    )
    profile.reward_program_snapshot = snapshot


async def refresh_program_profile_from_bitrix(
    db: AsyncSession,
    *,
    user: User,
    client: BitrixPromoClient | None = None,
    strict: bool = False,
) -> dict[str, Any] | None:
    profile = await ensure_default_reward_program(db, user=user)
    if not bitrix_promo_configured() or not user.email:
        profile.bitrix_sync_status = (
            "not_configured" if not bitrix_promo_configured() else "unlinked"
        )
        profile.bitrix_sync_error = (
            "Bitrix promo integration is not configured"
            if not bitrix_promo_configured()
            else "Customer email is missing"
        )
        await db.flush()
        return None

    try:
        response = await (client or BitrixPromoClient()).profile(
            bitrix_user_id=profile.bitrix_user_id,
            user_email=user.email,
        )
    except BitrixPromoError as error:
        profile.bitrix_sync_status = (
            "unlinked" if error.code == "user_not_found" else "failed"
        )
        profile.bitrix_sync_error = f"{error.code}: {error.message_en}"[:500]
        await db.flush()
        if strict and error.code != "user_not_found":
            raise
        return None
    except (RuntimeError, httpx.HTTPError) as error:
        profile.bitrix_sync_status = "failed"
        profile.bitrix_sync_error = str(error)[:500]
        await db.flush()
        if strict:
            raise
        return None

    program_profile = _program_profile(response)
    if program_profile is None:
        profile.bitrix_sync_status = "failed"
        profile.bitrix_sync_error = "Bitrix profile response is missing program_profile"
        await db.flush()
        return None

    raw_bitrix_user_id = (
        response.get("user_id")
        or program_profile.get("user_id")
        or profile.bitrix_user_id
    )
    bitrix_user_id = int(raw_bitrix_user_id or 0) or None
    apply_bitrix_program_profile(
        profile,
        user=user,
        program_profile=program_profile,
        bitrix_user_id=bitrix_user_id,
    )
    await db.flush()
    return program_profile


async def refresh_assigned_referrer_promo(
    db: AsyncSession,
    *,
    user: User,
    client: BitrixPromoClient | None = None,
) -> dict[str, Any] | None:
    program_profile = await refresh_program_profile_from_bitrix(
        db,
        user=user,
        client=client,
    )
    if program_profile is None:
        logger.info(
            "Bitrix program profile is unavailable for user_id=%s",
            user.id,
        )
    return program_profile
