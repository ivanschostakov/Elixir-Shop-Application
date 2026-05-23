from __future__ import annotations

import secrets
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.app.services.referrals import (
    ensure_own_promo_code,
    get_deposit_balance,
    get_or_create_referral_profile,
    profile_has_referral_participation,
    run_monthly_commission_calculation,
)
from src.app.services.referrals.calculations import calculate_personal_discount_percent, quantize_money
from src.app.services.referrals.ledger import DEPOSIT_ENTRY_TYPES
from src.database.crud.referrals import (
    create_manual_deposit_adjustment_entry,
    list_referral_commissions as list_referral_commission_rows,
    list_referral_deposits as list_referral_deposit_rows,
    list_referral_profiles as list_referral_profile_rows,
    list_referral_promo_codes as list_referral_promo_code_rows,
)
from src.database.models import ReferralProfile


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


async def set_initial_purchase_balance(db: AsyncSession, *, user_id: int, amount: Decimal) -> dict[str, Any]:
    profile = await get_or_create_referral_profile(db, user_id=user_id)
    profile.initial_purchase_balance = quantize_money(amount)
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


async def create_manual_deposit_adjustment(db: AsyncSession, *, user_id: int, amount: Decimal, direction: str, currency: str, note: str | None) -> dict[str, Any]:
    entry = await create_manual_deposit_adjustment_entry(
        db,
        user_id=user_id,
        amount=quantize_money(amount),
        direction=direction,
        currency=currency,
        note=note,
        idempotency_key=f"manual_deposit_adjustment:{user_id}:{secrets.token_urlsafe(12)}",
        effective_at=ufa_now(),
        commit=True,
    )
    return {"entry_id": entry.id, "balance": await get_deposit_balance(db, user_id)}


async def list_profiles(db: AsyncSession, *, limit: int, offset: int) -> list[dict[str, Any]]:
    profiles = await list_referral_profile_rows(db, limit=limit, offset=offset)
    return [_profile_row(profile, deposit_balance=await get_deposit_balance(db, profile.user_id)) for profile in profiles]


async def list_promo_codes(db: AsyncSession, *, limit: int, offset: int) -> list[dict[str, Any]]:
    promo_codes = await list_referral_promo_code_rows(db, limit=limit, offset=offset)
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


async def list_commissions(db: AsyncSession, *, limit: int, offset: int) -> list[dict[str, Any]]:
    entries = await list_referral_commission_rows(db, limit=limit, offset=offset)
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


async def list_deposits(db: AsyncSession, *, limit: int, offset: int, user_id: int | None) -> list[dict[str, Any]]:
    entries = await list_referral_deposit_rows(
        db,
        entry_types=DEPOSIT_ENTRY_TYPES,
        limit=limit,
        offset=offset,
        user_id=user_id,
    )
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


async def run_commissions(db: AsyncSession, *, period_start: date, period_end: date, dry_run: bool) -> dict[str, Any]:
    results = await run_monthly_commission_calculation(
        db,
        period_start=period_start,
        period_end=period_end,
        dry_run=dry_run,
    )
    if not dry_run:
        await db.commit()
    return {"dry_run": dry_run, "count": len(results), "entries": results}
