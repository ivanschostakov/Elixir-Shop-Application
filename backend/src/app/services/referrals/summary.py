import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services.benefits.moysklad_bonus import get_user_moysklad_bonus_wallet
from src.database.models import AppReferralAccrual, User
from src.integrations.bitrix_promo import (
    BitrixPromoClient,
    BitrixPromoError,
    bitrix_promo_configured,
)

from .bitrix_sync import refresh_assigned_referrer_promo
from .calculations import (
    PARTNER_UNLOCK_SPEND,
    next_personal_discount_threshold,
    quantize_money,
    quantize_percent,
)
from .profile import refresh_profile_discount
from .program import UNIFIED_REWARD_PROGRAM, ensure_unified_reward_program

logger = logging.getLogger(__name__)


async def _local_partner_totals(
    db: AsyncSession,
    *,
    user_id: int,
) -> tuple[Decimal, Decimal, Decimal]:
    totals = (
        await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                AppReferralAccrual.status == "pending",
                                AppReferralAccrual.commission_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                AppReferralAccrual.status == "approved",
                                AppReferralAccrual.commission_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                AppReferralAccrual.status == "rejected",
                                AppReferralAccrual.commission_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(AppReferralAccrual.beneficiary_user_id == user_id)
        )
    ).one()
    return (
        quantize_money(totals[0]),
        quantize_money(totals[1]),
        quantize_money(totals[2]),
    )


async def get_referral_profile_summary(db: AsyncSession, *, user: User) -> dict[str, Any]:
    profile = await ensure_unified_reward_program(db, user=user)
    bonus_wallet = await get_user_moysklad_bonus_wallet(user)

    own_promo_code = None
    suggested_promo_code = None
    referrer_promo_code = user.promo_code
    partner_pending, partner_approved, partner_rejected = (
        await _local_partner_totals(db, user_id=user.id)
    )
    network_monthly: dict[str, Any] = {}

    program_profile = await refresh_assigned_referrer_promo(db, user=user)
    if program_profile is not None:
        own_promo_code = program_profile.get("own_promo")
        suggested_promo_code = program_profile.get("suggested_promo")
        referrer_promo_code = (
            program_profile.get("referrer_promo") or user.promo_code
        )
    else:
        refresh_profile_discount(
            profile,
            has_promo_code=bool(referrer_promo_code),
        )

    if bitrix_promo_configured() and user.email:
        try:
            partner_summary = await BitrixPromoClient().partner_summary(
                bitrix_user_id=profile.bitrix_user_id,
                user_email=user.email,
            )
            raw_bitrix_user_id = int(partner_summary.get("user_id") or 0)
            if raw_bitrix_user_id > 0:
                profile.bitrix_user_id = raw_bitrix_user_id
            authoritative = partner_summary.get("app_partner_accruals")
            if isinstance(authoritative, dict):
                partner_pending = quantize_money(authoritative.get("pending_amount"))
                partner_approved = quantize_money(authoritative.get("approved_amount"))
                partner_rejected = quantize_money(authoritative.get("rejected_amount"))
            raw_network_monthly = partner_summary.get("network_monthly_bonus")
            if isinstance(raw_network_monthly, dict):
                network_monthly = raw_network_monthly
            own_promo_code = partner_summary.get("own_promo") or own_promo_code
            referrer_promo_code = (
                partner_summary.get("referrer_promo") or referrer_promo_code
            )
            participation_active = bool(referrer_promo_code)
            if (
                participation_active
                and partner_summary.get("personal_purchase_total") is not None
            ):
                profile.referral_discount_base_total = quantize_money(
                    partner_summary.get("personal_purchase_total")
                )
            elif not participation_active:
                profile.referral_discount_base_total = Decimal("0.00")
            if (
                participation_active
                and partner_summary.get("personal_discount_percent") is not None
            ):
                profile.current_discount_percent = quantize_percent(
                    max(
                        Decimal("3.00"),
                        Decimal(
                            str(
                                partner_summary.get(
                                    "personal_discount_percent"
                                )
                                or 0
                            )
                        ),
                    )
                )
            elif not participation_active:
                profile.current_discount_percent = Decimal("0.00")
            profile.bitrix_sync_status = "synced"
            profile.bitrix_synced_at = datetime.now(timezone.utc)
            profile.bitrix_sync_error = None
        except (BitrixPromoError, RuntimeError, httpx.HTTPError):
            logger.exception(
                "Could not load Bitrix partner summary for user_id=%s",
                user.id,
            )

    total_purchases = quantize_money(profile.referral_discount_base_total)
    if own_promo_code or total_purchases >= PARTNER_UNLOCK_SPEND:
        profile.partner_unlocked_at = (
            profile.partner_unlocked_at or datetime.now(timezone.utc)
        )
    partner_unlocked = profile.partner_unlocked_at is not None
    participation_active = bool(referrer_promo_code)
    next_threshold = (
        next_personal_discount_threshold(total_purchases)
        if participation_active
        else None
    )
    next_remaining = (
        quantize_money(max(Decimal("0.00"), next_threshold - total_purchases))
        if next_threshold is not None
        else Decimal("0.00")
    )
    partner_remaining = quantize_money(
        max(Decimal("0.00"), PARTNER_UNLOCK_SPEND - total_purchases)
    )

    return {
        "user_id": user.id,
        "reward_program": UNIFIED_REWARD_PROGRAM,
        "reward_program_selected_at": profile.reward_program_selected_at,
        "reward_program_selection_source": profile.reward_program_selection_source,
        "program_selection_required": False,
        "bonus_program_enabled": participation_active,
        "partner_program_unlocked": partner_unlocked,
        "partner_program_status": (
            "active"
            if own_promo_code
            else "eligible"
            if partner_unlocked
            else "locked"
        ),
        "partner_unlock_threshold": PARTNER_UNLOCK_SPEND,
        "partner_unlock_remaining": partner_remaining,
        "personal_discount_next_threshold": next_threshold,
        "personal_discount_remaining": next_remaining,
        "bitrix_profile_found": profile.bitrix_sync_status == "synced",
        "bitrix_sync_status": profile.bitrix_sync_status,
        "bitrix_synced_at": profile.bitrix_synced_at,
        "bitrix_user_id": profile.bitrix_user_id,
        "total_purchases": total_purchases,
        "current_discount_percent": quantize_percent(profile.current_discount_percent),
        "promo_code": referrer_promo_code,
        "own_promo_code": own_promo_code,
        "suggested_promo_code": suggested_promo_code,
        "referrer_promo_code": referrer_promo_code,
        "referral_discount_base_total": total_purchases,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "bonus_points": bonus_wallet.balance_points,
        "bonus_rubles": bonus_wallet.balance_rubles,
        "bonus_wallet_available": bonus_wallet.is_loaded,
        "bonus_program_name": "Бонусные рубли",
        "bonus_spend_rate_points_to_ruble": bonus_wallet.spend_rate_points_to_ruble,
        "bonus_max_paid_rate_percent": bonus_wallet.max_paid_rate_percent,
        "partner_pending_rubles": partner_pending,
        "partner_approved_rubles": partner_approved,
        "partner_rejected_rubles": partner_rejected,
        # Compatibility alias for installed clients. The spendable balance
        # always comes from the authoritative MoySklad wallet.
        "partner_site_balance_rubles": bonus_wallet.balance_rubles,
        "partner_network_period": network_monthly.get("period"),
        "partner_network_status": network_monthly.get("status"),
        "partner_network_turnover": quantize_money(
            network_monthly.get("network_turnover")
        ),
        "partner_network_rate_percent": quantize_percent(
            network_monthly.get("rate_percent")
        ),
        "partner_network_amount": quantize_money(network_monthly.get("amount")),
    }
