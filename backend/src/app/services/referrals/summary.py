import logging
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
from .calculations import quantize_money, quantize_percent
from .profile import (
    get_or_create_referral_profile,
    referral_profile_total_purchases,
    refresh_profile_discount,
)
from .program import normalize_reward_program

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
    profile = await get_or_create_referral_profile(db, user=user)
    reward_program = normalize_reward_program(profile.reward_program)
    bonus_wallet = await get_user_moysklad_bonus_wallet(user)

    own_promo_code = None
    referrer_promo_code = None
    partner_pending = Decimal("0.00")
    partner_approved = Decimal("0.00")
    partner_rejected = Decimal("0.00")
    site_partner_balance = Decimal("0.00")
    network_monthly: dict[str, Any] = {}

    if reward_program == "bonus":
        refresh_profile_discount(profile)
    elif reward_program == "partner":
        referrer_promo_code = user.promo_code
        program_profile = await refresh_assigned_referrer_promo(db, user=user)
        if program_profile is not None:
            try:
                own_promo_code = program_profile.get("own_promo")
                referrer_promo_code = program_profile.get("referrer_promo")
                order_sum = program_profile.get("order_sum")
                if isinstance(order_sum, dict) and order_sum.get("amount") is not None:
                    profile.referral_discount_base_total = quantize_money(order_sum["amount"])
                stored_percent = Decimal(
                    str(program_profile.get("stored_discount_percent") or 0)
                )
                group_percent = Decimal(
                    str(program_profile.get("group_discount_percent") or 0)
                )
                profile.current_discount_percent = quantize_percent(
                    max(Decimal("0"), stored_percent, group_percent)
                )
            except (ValueError, TypeError):
                logger.exception(
                    "Could not apply Bitrix partner profile for user_id=%s",
                    user.id,
                )

        partner_pending, partner_approved, partner_rejected = (
            await _local_partner_totals(db, user_id=user.id)
        )
        if bitrix_promo_configured() and user.email:
            try:
                partner_summary = await BitrixPromoClient().partner_summary(
                    user_email=user.email,
                )
                authoritative = partner_summary.get("app_partner_accruals")
                if isinstance(authoritative, dict):
                    partner_pending = quantize_money(authoritative.get("pending_amount"))
                    partner_approved = quantize_money(authoritative.get("approved_amount"))
                    partner_rejected = quantize_money(authoritative.get("rejected_amount"))
                site_partner_balance = quantize_money(
                    partner_summary.get("site_partner_balance")
                )
                raw_network_monthly = partner_summary.get("network_monthly_bonus")
                if isinstance(raw_network_monthly, dict):
                    network_monthly = raw_network_monthly
                own_promo_code = partner_summary.get("own_promo") or own_promo_code
                referrer_promo_code = (
                    partner_summary.get("referrer_promo") or referrer_promo_code
                )
            except (BitrixPromoError, RuntimeError, httpx.HTTPError):
                logger.exception(
                    "Could not load Bitrix partner summary for user_id=%s",
                    user.id,
                )

    return {
        "user_id": user.id,
        "reward_program": reward_program,
        "reward_program_selected_at": profile.reward_program_selected_at,
        "reward_program_selection_source": profile.reward_program_selection_source,
        "program_selection_required": reward_program is None,
        "bitrix_user_id": profile.bitrix_user_id,
        "total_purchases": referral_profile_total_purchases(profile),
        "current_discount_percent": quantize_percent(profile.current_discount_percent),
        "promo_code": referrer_promo_code,
        "own_promo_code": own_promo_code,
        "referrer_promo_code": referrer_promo_code,
        "referral_discount_base_total": quantize_money(
            profile.referral_discount_base_total
        ),
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "bonus_points": bonus_wallet.balance_points,
        "bonus_rubles": bonus_wallet.balance_rubles,
        "bonus_program_name": bonus_wallet.program_name,
        "bonus_spend_rate_points_to_ruble": bonus_wallet.spend_rate_points_to_ruble,
        "bonus_max_paid_rate_percent": bonus_wallet.max_paid_rate_percent,
        "partner_pending_rubles": partner_pending,
        "partner_approved_rubles": partner_approved,
        "partner_rejected_rubles": partner_rejected,
        "partner_site_balance_rubles": site_partner_balance,
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
