from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.app.services.referrals.calculations import (
    PARTNER_UNLOCK_SPEND,
    quantize_money,
)
from src.app.services.referrals.program import normalize_reward_program
from src.database.crud.referrals import list_referral_profiles as list_referral_profile_rows
from src.database.models import AppReferralAccrual, AppReferralPurchase, ReferralProfile


def profile_row(profile: ReferralProfile) -> dict[str, Any]:
    total = quantize_money(profile.referral_discount_base_total)
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "reward_program": normalize_reward_program(profile.reward_program) or "bonus",
        "reward_program_selected_at": profile.reward_program_selected_at,
        "reward_program_selection_source": profile.reward_program_selection_source,
        "bitrix_user_id": profile.bitrix_user_id,
        "bitrix_sync_status": profile.bitrix_sync_status,
        "bitrix_synced_at": profile.bitrix_synced_at,
        "partner_unlocked_at": profile.partner_unlocked_at,
        "partner_program_status": (
            "active"
            if profile.partner_unlocked_at is not None
            or total >= PARTNER_UNLOCK_SPEND
            else "locked"
        ),
        "total_purchases": total,
        "referral_discount_base_total": total,
        "current_discount_percent": profile.current_discount_percent,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


async def list_profiles(db: AsyncSession, *, limit: int, offset: int) -> list[dict[str, Any]]:
    profiles = await list_referral_profile_rows(db, limit=limit, offset=offset)
    return [profile_row(profile) for profile in profiles]


def _accrual_row(accrual: AppReferralAccrual) -> dict[str, Any]:
    purchase = accrual.purchase
    return {
        "id": accrual.id,
        "purchase_id": purchase.id,
        "order_id": purchase.order_id,
        "external_order_id": purchase.external_order_id,
        "buyer_user_id": purchase.buyer_user_id,
        "beneficiary_user_id": accrual.beneficiary_user_id,
        "beneficiary_bitrix_user_id": accrual.beneficiary_bitrix_user_id,
        "beneficiary_email": accrual.beneficiary_email,
        "beneficiary_name": accrual.beneficiary_name,
        "promo_code": purchase.promo_code,
        "period": purchase.period_start.strftime("%Y-%m"),
        "level": accrual.level,
        "buyer_discount_percent": accrual.buyer_discount_percent,
        "referrer_discount_percent": accrual.referrer_discount_percent,
        "commission_percent": accrual.commission_percent,
        "order_amount": purchase.amount,
        "commission_amount": accrual.commission_amount,
        "currency": accrual.currency,
        "status": accrual.status,
        "reason": accrual.reason,
        "wallet_sync_status": accrual.wallet_sync_status,
        "bonus_points_credited": accrual.bonus_points_credited,
        "bonus_rubles_credited": accrual.bonus_rubles_credited,
        "wallet_synced_at": accrual.wallet_synced_at,
        "wallet_sync_error": accrual.wallet_sync_error,
        "settlement_method": accrual.settlement_method,
        "settlement_reference": accrual.settlement_reference,
        "settled_at": accrual.settled_at,
        "settled_by_admin_user_id": accrual.settled_by_admin_user_id,
        "wallet_reversed_at": accrual.wallet_reversed_at,
        "bitrix_sync_status": purchase.bitrix_sync_status,
        "paid_at": purchase.paid_at,
        "created_at": accrual.created_at,
        "updated_at": accrual.updated_at,
    }


async def list_accruals(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    status: str | None,
    period: str | None,
) -> list[dict[str, Any]]:
    stmt = (
        select(AppReferralAccrual)
        .join(AppReferralPurchase)
        .options(joinedload(AppReferralAccrual.purchase))
        .order_by(AppReferralAccrual.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if status:
        stmt = stmt.where(AppReferralAccrual.status == status)
    if period:
        stmt = stmt.where(
            func.to_char(AppReferralPurchase.period_start, "YYYY-MM") == period
        )
    rows = list((await db.execute(stmt)).scalars().unique().all())
    return [_accrual_row(row) for row in rows]


async def list_settlements(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    period: str | None,
) -> list[dict[str, Any]]:
    period_column = func.to_char(AppReferralPurchase.period_start, "YYYY-MM")
    deposited_case = case(
        (
            AppReferralAccrual.wallet_sync_status == "credited",
            AppReferralAccrual.commission_amount,
        ),
        else_=0,
    )
    transferred_case = case(
        (
            AppReferralAccrual.wallet_sync_status == "transferred",
            AppReferralAccrual.commission_amount,
        ),
        else_=0,
    )
    stmt = (
        select(
            AppReferralAccrual.beneficiary_user_id,
            AppReferralAccrual.beneficiary_bitrix_user_id,
            AppReferralAccrual.beneficiary_email,
            AppReferralAccrual.beneficiary_name,
            period_column.label("period"),
            AppReferralAccrual.currency,
            func.count(AppReferralAccrual.id),
            func.coalesce(func.sum(AppReferralAccrual.commission_amount), 0),
            func.coalesce(func.sum(deposited_case), 0),
            func.coalesce(func.sum(transferred_case), 0),
        )
        .join(AppReferralPurchase)
        .where(AppReferralAccrual.status == "approved")
        .group_by(
            AppReferralAccrual.beneficiary_user_id,
            AppReferralAccrual.beneficiary_bitrix_user_id,
            AppReferralAccrual.beneficiary_email,
            AppReferralAccrual.beneficiary_name,
            period_column,
            AppReferralAccrual.currency,
        )
        .order_by(period_column.desc(), AppReferralAccrual.beneficiary_bitrix_user_id.asc())
        .limit(limit)
        .offset(offset)
    )
    if period:
        stmt = stmt.where(period_column == period)
    rows = (await db.execute(stmt)).all()
    result: list[dict[str, Any]] = []
    for row in rows:
        approved = quantize_money(row[7])
        deposited = quantize_money(row[8])
        transferred = quantize_money(row[9])
        awaiting = quantize_money(
            max(0, approved - deposited - transferred)
        )
        result.append({
            "beneficiary_user_id": row[0],
            "beneficiary_bitrix_user_id": row[1],
            "beneficiary_email": row[2],
            "beneficiary_name": row[3],
            "period": row[4],
            "currency": row[5],
            "accruals_count": int(row[6] or 0),
            "approved_amount": approved,
            "deposited_amount": deposited,
            "transferred_amount": transferred,
            "awaiting_deposit_amount": awaiting,
            "awaiting_settlement_amount": awaiting,
        })
    return result


async def mark_settlement_transferred(
    db: AsyncSession,
    *,
    beneficiary_bitrix_user_id: int,
    period: str,
    currency: str,
    reference: str,
    admin_user_id: int,
) -> dict[str, Any] | None:
    normalized_currency = currency.strip().upper()
    base_conditions = (
        AppReferralAccrual.status == "approved",
        AppReferralAccrual.beneficiary_bitrix_user_id == beneficiary_bitrix_user_id,
        func.to_char(AppReferralPurchase.period_start, "YYYY-MM") == period,
        func.upper(AppReferralAccrual.currency) == normalized_currency,
    )
    candidates = list(
        (
            await db.execute(
                select(AppReferralAccrual)
                .join(AppReferralPurchase)
                .where(
                    *base_conditions,
                    AppReferralAccrual.wallet_sync_status.in_(
                        ("pending", "waiting_for_wallet", "failed")
                    ),
                )
                .order_by(AppReferralAccrual.id)
                .with_for_update()
            )
        ).scalars().all()
    )
    if not candidates:
        candidates = list(
            (
                await db.execute(
                    select(AppReferralAccrual)
                    .join(AppReferralPurchase)
                    .where(
                        *base_conditions,
                        AppReferralAccrual.wallet_sync_status == "transferred",
                        AppReferralAccrual.settlement_reference == reference,
                    )
                    .order_by(AppReferralAccrual.id)
                )
            ).scalars().all()
        )
        if not candidates:
            return None

    settled_at = candidates[0].settled_at or datetime.now(timezone.utc)
    for accrual in candidates:
        accrual.settlement_method = "transfer"
        accrual.settlement_reference = reference
        accrual.settled_at = settled_at
        accrual.settled_by_admin_user_id = admin_user_id
        accrual.wallet_sync_status = "transferred"
        accrual.wallet_sync_error = None

    return {
        "beneficiary_bitrix_user_id": beneficiary_bitrix_user_id,
        "period": period,
        "currency": normalized_currency,
        "reference": reference,
        "accruals_count": len(candidates),
        "transferred_amount": quantize_money(
            sum((row.commission_amount for row in candidates), start=0)
        ),
        "settled_at": settled_at,
    }


async def referral_summary(db: AsyncSession) -> dict[str, Any]:
    totals = (await db.execute(select(
        func.count(ReferralProfile.id),
        func.coalesce(func.sum(ReferralProfile.referral_discount_base_total), 0),
        func.coalesce(func.avg(ReferralProfile.current_discount_percent), 0),
        func.coalesce(func.max(ReferralProfile.current_discount_percent), 0),
        func.coalesce(
            func.sum(
                case(
                    (
                        (ReferralProfile.partner_unlocked_at.is_not(None))
                        | (
                            ReferralProfile.referral_discount_base_total
                            >= PARTNER_UNLOCK_SPEND
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ),
    ))).one()
    band_rows = (await db.execute(select(
        case(
            (ReferralProfile.current_discount_percent <= 0, "0%"),
            (ReferralProfile.current_discount_percent < 5, "1–4%"),
            (ReferralProfile.current_discount_percent < 10, "5–9%"),
            else_="10%+",
        ).label("band"),
        func.count(ReferralProfile.id),
    ).group_by("band"))).all()
    accrual_totals = (
        await db.execute(
            select(
                func.count(AppReferralAccrual.id),
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
            )
        )
    ).one()
    return {
        "profiles_count": int(totals[0] or 0),
        "total_discount_base": quantize_money(totals[1] or 0),
        "average_discount_percent": totals[2] or 0,
        "max_discount_percent": totals[3] or 0,
        "active_referrers_count": int(totals[4] or 0),
        "discount_bands": [{"band": str(band), "count": int(count)} for band, count in band_rows],
        "accruals_count": int(accrual_totals[0] or 0),
        "pending_accrual_amount": quantize_money(accrual_totals[1] or 0),
        "approved_accrual_amount": quantize_money(accrual_totals[2] or 0),
        "rejected_accrual_amount": quantize_money(accrual_totals[3] or 0),
    }
