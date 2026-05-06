import secrets
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import ufa_now
from src.app.modules.auth.dependencies import get_current_admin_user
from src.app.services.referrals import (
    ensure_own_promo_code,
    get_deposit_balance,
    get_or_create_referral_profile,
    profile_has_referral_participation,
    run_monthly_commission_calculation,
)
from src.app.services.referrals.calculations import calculate_personal_discount_percent, quantize_money
from src.app.services.referrals.service import DEPOSIT_ENTRY_TYPES
from src.database import get_db
from src.database.limits import CURRENCY_CODE_MAX_LENGTH, LEDGER_NOTE_MAX_LENGTH, PROMO_CODE_MAX_LENGTH
from src.database.models import BusinessLedgerEntry, ReferralCommissionEntry, ReferralProfile, ReferralPromoCode, User

admin_referrals_router = APIRouter(prefix="/admin/referrals", tags=["admin_referrals"])


class InitialPurchaseBalancePayload(BaseModel):
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class ManualDepositAdjustmentPayload(BaseModel):
    user_id: int = Field(ge=1)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    direction: Literal["credit", "debit"]
    currency: str = Field(default="RUB", max_length=CURRENCY_CODE_MAX_LENGTH)
    note: str | None = Field(default=None, max_length=LEDGER_NOTE_MAX_LENGTH)


class CommissionRunPayload(BaseModel):
    period_start: date
    period_end: date
    dry_run: bool = True


def _profile_row(profile: ReferralProfile, *, deposit_balance: Decimal | None = None) -> dict[str, Any]:
    total = quantize_money(profile.initial_purchase_balance) + quantize_money(profile.website_seed_purchase_balance) + quantize_money(profile.app_paid_purchase_total)
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "website_identity_id": profile.website_identity_id,
        "initial_purchase_balance": quantize_money(profile.initial_purchase_balance),
        "website_seed_purchase_balance": quantize_money(profile.website_seed_purchase_balance),
        "app_paid_purchase_total": quantize_money(profile.app_paid_purchase_total),
        "total_purchases": total,
        "current_discount_percent": profile.current_discount_percent,
        "referrer_promo_code": profile.referrer_promo_code,
        "referrer_user_id": profile.referrer_user_id,
        "own_promo_code": profile.own_promo_code,
        "deposit_balance": deposit_balance,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


@admin_referrals_router.patch("/profiles/{user_id}/initial-balance", status_code=status.HTTP_200_OK)
async def set_referral_initial_purchase_balance(
    user_id: int,
    payload: InitialPurchaseBalancePayload,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    profile = await get_or_create_referral_profile(db, user_id=user_id)
    profile.initial_purchase_balance = quantize_money(payload.amount)
    if profile_has_referral_participation(profile):
        profile.referral_discount_base_total = (
            quantize_money(profile.initial_purchase_balance)
            + quantize_money(profile.website_seed_purchase_balance)
            + quantize_money(profile.app_paid_purchase_total)
        )
        profile.current_discount_percent = calculate_personal_discount_percent(profile.referral_discount_base_total, has_referrer=True)
    await ensure_own_promo_code(db, profile)
    await db.commit()
    await db.refresh(profile)
    return _profile_row(profile, deposit_balance=await get_deposit_balance(db, user_id))


@admin_referrals_router.post("/deposit-adjustments", status_code=status.HTTP_201_CREATED)
async def create_manual_deposit_adjustment(
    payload: ManualDepositAdjustmentPayload,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    entry = BusinessLedgerEntry(
        user_id=payload.user_id,
        entry_type="manual_adjustment",
        direction=payload.direction,
        amount=quantize_money(payload.amount),
        currency=payload.currency,
        source_system="admin",
        source_code=None,
        status="posted",
        effective_at=ufa_now(),
        note=payload.note,
        idempotency_key=f"manual_deposit_adjustment:{payload.user_id}:{secrets.token_urlsafe(12)}",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {"entry_id": entry.id, "balance": await get_deposit_balance(db, payload.user_id)}


@admin_referrals_router.get("/profiles", status_code=status.HTTP_200_OK)
async def list_referral_profiles(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> list[dict[str, Any]]:
    profiles = list(
        (
            await db.execute(select(ReferralProfile).order_by(ReferralProfile.id.desc()).limit(limit).offset(offset))
        ).scalars().all()
    )
    return [_profile_row(profile, deposit_balance=await get_deposit_balance(db, profile.user_id)) for profile in profiles]


@admin_referrals_router.get("/promo-codes", status_code=status.HTTP_200_OK)
async def list_referral_promo_codes(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> list[dict[str, Any]]:
    promo_codes = list(
        (
            await db.execute(select(ReferralPromoCode).order_by(ReferralPromoCode.id.desc()).limit(limit).offset(offset))
        ).scalars().all()
    )
    return [
        {
            "id": promo.id,
            "code": promo.code,
            "owner_user_id": promo.owner_user_id,
            "is_active": promo.is_active,
            "source_system": promo.source_system,
            "issued_at": promo.issued_at,
            "created_at": promo.created_at,
        }
        for promo in promo_codes
    ]


@admin_referrals_router.get("/commissions", status_code=status.HTTP_200_OK)
async def list_referral_commissions(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> list[dict[str, Any]]:
    entries = list(
        (
            await db.execute(select(ReferralCommissionEntry).order_by(ReferralCommissionEntry.id.desc()).limit(limit).offset(offset))
        ).scalars().all()
    )
    return [
        {
            "id": entry.id,
            "period_start": entry.period_start,
            "period_end": entry.period_end,
            "order_id": entry.order_id,
            "buyer_user_id": entry.buyer_user_id,
            "referrer_user_id": entry.referrer_user_id,
            "level": entry.level,
            "promo_code": entry.promo_code,
            "commission_percent": entry.commission_percent,
            "commission_amount": entry.commission_amount,
            "currency": entry.currency,
            "status": entry.status,
            "posted_at": entry.posted_at,
        }
        for entry in entries
    ]


@admin_referrals_router.get("/deposits", status_code=status.HTTP_200_OK)
async def list_referral_deposits(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> list[dict[str, Any]]:
    stmt = (
        select(BusinessLedgerEntry)
        .where(BusinessLedgerEntry.entry_type.in_(DEPOSIT_ENTRY_TYPES))
        .order_by(BusinessLedgerEntry.effective_at.desc(), BusinessLedgerEntry.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if user_id is not None:
        stmt = stmt.where(BusinessLedgerEntry.user_id == user_id)
    entries = list((await db.execute(stmt)).scalars().all())
    return [
        {
            "id": entry.id,
            "user_id": entry.user_id,
            "entry_type": entry.entry_type,
            "direction": entry.direction,
            "amount": entry.amount,
            "currency": entry.currency,
            "source_system": entry.source_system,
            "source_code": entry.source_code,
            "status": entry.status,
            "note": entry.note,
            "effective_at": entry.effective_at,
        }
        for entry in entries
    ]


@admin_referrals_router.post("/commissions/run", status_code=status.HTTP_200_OK)
async def run_referral_commissions(
    payload: CommissionRunPayload,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    results = await run_monthly_commission_calculation(db, period_start=payload.period_start, period_end=payload.period_end, dry_run=payload.dry_run)
    if not payload.dry_run:
        await db.commit()
    return {"dry_run": payload.dry_run, "count": len(results), "entries": results}
