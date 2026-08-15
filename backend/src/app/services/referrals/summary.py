import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import LOYALTY_ORDER_CASHBACK_PERCENT, ufa_now
from src.app.services.benefits.loyalty import (
    loyalty_bonus_expiration_summary,
    pending_loyalty_bonus_points,
)
from src.app.services.benefits.moysklad_bonus import (
    bonus_points_to_rubles,
    get_user_moysklad_bonus_wallet,
)
from src.database.models import AppReferralAccrual, Order, User
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
from .program import (
    ensure_default_reward_program,
    normalize_reward_program,
    reward_program_selection_available,
    reward_program_selection_required,
)

logger = logging.getLogger(__name__)


def _month_bounds(anchor: datetime, months_back: int = 0) -> tuple[datetime, datetime]:
    year = anchor.year
    month = anchor.month - months_back
    while month <= 0:
        year -= 1
        month += 12
    start = datetime(year, month, 1, tzinfo=anchor.tzinfo or timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=start.tzinfo)
    else:
        end = datetime(year, month + 1, 1, tzinfo=start.tzinfo)
    return start, end


async def _local_month_purchase_total(
    db: AsyncSession,
    *,
    user_id: int,
    start: datetime,
    end: datetime,
) -> Decimal:
    value = (
        await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        func.greatest(
                            Decimal("0.00"),
                            Order.grand_total - Order.delivery_total,
                        )
                    ),
                    0,
                )
            ).where(
                Order.user_id == user_id,
                Order.is_paid.is_(True),
                Order.is_canceled.is_(False),
                Order.payment_paid_at.is_not(None),
                Order.payment_paid_at >= start,
                Order.payment_paid_at < end,
            )
        )
    ).scalar_one()
    return quantize_money(value)


async def _local_partner_totals(
    db: AsyncSession,
    *,
    user_id: int,
) -> tuple[Decimal, Decimal, Decimal]:
    totals = (
        await db.execute(
            select(
                *(
                    func.coalesce(
                        func.sum(
                            case(
                                (AppReferralAccrual.status == state, AppReferralAccrual.commission_amount),
                                else_=0,
                            )
                        ),
                        0,
                    )
                    for state in ("pending", "approved", "rejected")
                )
            ).where(AppReferralAccrual.beneficiary_user_id == user_id)
        )
    ).one()
    return tuple(quantize_money(value) for value in totals)  # type: ignore[return-value]


async def get_referral_profile_summary(db: AsyncSession, *, user: User) -> dict[str, Any]:
    profile = await ensure_default_reward_program(db, user=user)
    reward_program = normalize_reward_program(profile.reward_program) or "bonus"
    bonus_wallet = await get_user_moysklad_bonus_wallet(user)
    pending_bonus_points = await pending_loyalty_bonus_points(db, user_id=user.id)
    pending_bonus_rubles = bonus_points_to_rubles(
        pending_bonus_points,
        bonus_wallet.spend_rate_points_to_ruble,
    )
    expiration = await loyalty_bonus_expiration_summary(db, user_id=user.id)
    expiring_points = int(expiration["expiring_points"])
    expiring_rubles = bonus_points_to_rubles(
        expiring_points,
        bonus_wallet.spend_rate_points_to_ruble,
    )

    now = ufa_now()
    current_start, current_end = _month_bounds(now)
    previous_start, previous_end = _month_bounds(now, 1)
    current_month_purchases = await _local_month_purchase_total(
        db, user_id=user.id, start=current_start, end=current_end
    )
    previous_month_purchases = await _local_month_purchase_total(
        db, user_id=user.id, start=previous_start, end=previous_end
    )

    own_promo_code = None
    suggested_promo_code = None
    referrer_promo_code = user.promo_code
    partner_pending, partner_approved, partner_rejected = (
        await _local_partner_totals(db, user_id=user.id)
    )

    program_profile = await refresh_assigned_referrer_promo(db, user=user)
    if program_profile is not None:
        own_promo_code = program_profile.get("own_promo")
        suggested_promo_code = program_profile.get("suggested_promo")
        referrer_promo_code = program_profile.get("referrer_promo") or user.promo_code
    else:
        refresh_profile_discount(profile, has_promo_code=bool(referrer_promo_code))
    reward_program = normalize_reward_program(profile.reward_program) or (
        "partner" if referrer_promo_code else "bonus"
    )

    remote_monthly_eligible: bool | None = None
    if bitrix_promo_configured() and user.email:
        try:
            partner_summary = await BitrixPromoClient().partner_summary(
                bitrix_user_id=profile.bitrix_user_id,
                user_email=user.email,
            )
            raw_bitrix_user_id = int(partner_summary.get("user_id") or 0)
            if raw_bitrix_user_id > 0:
                profile.bitrix_user_id = raw_bitrix_user_id
            if partner_summary.get("personal_purchase_total") is not None:
                profile.referral_discount_base_total = max(
                    quantize_money(profile.referral_discount_base_total),
                    quantize_money(partner_summary.get("personal_purchase_total")),
                )
            if partner_summary.get("current_month_purchases") is not None:
                current_month_purchases = max(
                    current_month_purchases,
                    quantize_money(partner_summary.get("current_month_purchases")),
                )
            if partner_summary.get("previous_month_purchases") is not None:
                previous_month_purchases = max(
                    previous_month_purchases,
                    quantize_money(partner_summary.get("previous_month_purchases")),
                )
            if reward_program == "partner":
                authoritative = partner_summary.get("app_partner_accruals")
                if isinstance(authoritative, dict):
                    partner_pending = quantize_money(authoritative.get("pending_amount"))
                    partner_approved = quantize_money(authoritative.get("approved_amount"))
                    partner_rejected = quantize_money(authoritative.get("rejected_amount"))
                own_promo_code = partner_summary.get("own_promo") or own_promo_code
                suggested_promo_code = partner_summary.get("suggested_promo") or suggested_promo_code
                referrer_promo_code = partner_summary.get("referrer_promo") or referrer_promo_code
                if partner_summary.get("personal_discount_percent") is not None:
                    profile.current_discount_percent = quantize_percent(
                        partner_summary.get("personal_discount_percent")
                    ) if referrer_promo_code else Decimal("0.00")
                eligibility = partner_summary.get("monthly_eligibility")
                if isinstance(eligibility, dict):
                    remote_monthly_eligible = (
                        eligibility.get("status") == "approved"
                        or (
                            eligibility.get("status") == "pending"
                            and quantize_money(
                                eligibility.get("lifetime_purchase_total")
                            ) >= PARTNER_UNLOCK_SPEND
                            and current_month_purchases >= Decimal("10000.00")
                        )
                    )
            else:
                own_promo_code = partner_summary.get("own_promo") or own_promo_code
                suggested_promo_code = partner_summary.get("suggested_promo") or suggested_promo_code
                referrer_promo_code = partner_summary.get("referrer_promo") or referrer_promo_code
                refresh_profile_discount(profile, has_promo_code=bool(referrer_promo_code))
            profile.bitrix_sync_status = "synced"
            profile.bitrix_synced_at = datetime.now(timezone.utc)
            profile.bitrix_sync_error = None
        except (BitrixPromoError, RuntimeError, httpx.HTTPError):
            logger.exception("Could not load Bitrix partner summary for user_id=%s", user.id)

    total_purchases = quantize_money(profile.referral_discount_base_total)
    if own_promo_code or total_purchases >= PARTNER_UNLOCK_SPEND:
        profile.partner_unlocked_at = profile.partner_unlocked_at or datetime.now(timezone.utc)
    partner_unlocked = profile.partner_unlocked_at is not None
    participation_active = reward_program == "partner" and bool(referrer_promo_code)
    next_threshold = next_personal_discount_threshold(total_purchases) if participation_active else None
    next_remaining = (
        quantize_money(max(Decimal("0.00"), next_threshold - total_purchases))
        if next_threshold is not None
        else Decimal("0.00")
    )
    partner_remaining = quantize_money(max(Decimal("0.00"), PARTNER_UNLOCK_SPEND - total_purchases))

    return {
        "user_id": user.id,
        "reward_program": reward_program,
        "reward_program_selected_at": profile.reward_program_selected_at,
        "reward_program_selection_source": profile.reward_program_selection_source,
        "program_selection_available": reward_program_selection_available(profile),
        "program_selection_required": reward_program_selection_required(profile),
        "bonus_program_enabled": reward_program == "bonus",
        "partner_program_unlocked": partner_unlocked,
        "partner_program_status": "active" if reward_program == "partner" else "eligible" if partner_unlocked else "locked",
        "partner_unlock_threshold": PARTNER_UNLOCK_SPEND,
        "partner_unlock_remaining": partner_remaining,
        "personal_discount_next_threshold": next_threshold,
        "personal_discount_remaining": next_remaining,
        "bitrix_profile_found": profile.bitrix_sync_status == "synced",
        "bitrix_sync_status": profile.bitrix_sync_status,
        "bitrix_synced_at": profile.bitrix_synced_at,
        "bitrix_user_id": profile.bitrix_user_id,
        "total_purchases": total_purchases,
        "current_month_purchases": current_month_purchases,
        "previous_month_purchases": previous_month_purchases,
        "current_discount_percent": quantize_percent(profile.current_discount_percent),
        "promo_code": referrer_promo_code,
        "own_promo_code": own_promo_code,
        "suggested_promo_code": suggested_promo_code,
        "referrer_promo_code": referrer_promo_code,
        "referral_discount_base_total": total_purchases,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "bonus_points": bonus_wallet.balance_points + pending_bonus_points,
        "bonus_rubles": bonus_wallet.balance_rubles + pending_bonus_rubles,
        "bonus_cashback_percent": Decimal(
            max(0, min(100, int(LOYALTY_ORDER_CASHBACK_PERCENT)))
        ),
        "bonus_wallet_available": bonus_wallet.is_loaded or pending_bonus_points > 0,
        "bonus_program_name": "Бонусные рубли",
        "bonus_spend_rate_points_to_ruble": bonus_wallet.spend_rate_points_to_ruble,
        "bonus_max_paid_rate_percent": Decimal("100.00"),
        "bonus_next_expiration_at": expiration["next_expires_at"],
        "bonus_expiring_points": expiring_points,
        "bonus_expiring_rubles": expiring_rubles,
        "bonus_expiry_warning_days": int(expiration["warning_days"]),
        "partner_pending_rubles": partner_pending,
        "partner_approved_rubles": partner_approved,
        "partner_rejected_rubles": partner_rejected,
        "partner_site_balance_rubles": bonus_wallet.balance_rubles + pending_bonus_rubles,
        "partner_monthly_minimum": Decimal("10000.00"),
        "partner_monthly_eligible": remote_monthly_eligible if remote_monthly_eligible is not None else total_purchases >= PARTNER_UNLOCK_SPEND and current_month_purchases >= Decimal("10000.00"),
        # Retained as zero-value compatibility fields for clients from the
        # experimental network-turnover release. That extra scheme is disabled.
        "partner_network_period": None,
        "partner_network_status": None,
        "partner_network_turnover": Decimal("0.00"),
        "partner_network_rate_percent": Decimal("0.00"),
        "partner_network_amount": Decimal("0.00"),
    }
