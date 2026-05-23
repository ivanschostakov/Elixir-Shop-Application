from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    BusinessLedgerEntry,
    ReferralCommissionEntry,
    ReferralProfile,
    ReferralPromoCode,
)


async def create_manual_deposit_adjustment_entry(session: AsyncSession, *, user_id: int, amount: Decimal, direction: str, currency: str, note: str | None, idempotency_key: str, effective_at: datetime, commit: bool = True) -> BusinessLedgerEntry:
    entry = BusinessLedgerEntry(
        user_id=user_id,
        entry_type="manual_adjustment",
        direction=direction,
        amount=amount,
        currency=currency,
        source_system="admin",
        source_code=None,
        status="posted",
        effective_at=effective_at,
        note=note,
        idempotency_key=idempotency_key,
    )
    session.add(entry)
    await session.flush()

    if commit:
        await session.commit()
        await session.refresh(entry)

    return entry


async def list_referral_profiles(session: AsyncSession, *, limit: int, offset: int) -> list[ReferralProfile]:
    stmt = select(ReferralProfile).order_by(ReferralProfile.id.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


async def list_referral_promo_codes(session: AsyncSession, *, limit: int, offset: int) -> list[ReferralPromoCode]:
    stmt = select(ReferralPromoCode).order_by(ReferralPromoCode.id.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


async def list_referral_commissions(session: AsyncSession, *, limit: int, offset: int) -> list[ReferralCommissionEntry]:
    stmt = select(ReferralCommissionEntry).order_by(ReferralCommissionEntry.id.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


async def list_referral_deposits(session: AsyncSession, *, entry_types: set[str], limit: int, offset: int, user_id: int | None = None) -> list[BusinessLedgerEntry]:
    stmt = (
        select(BusinessLedgerEntry)
        .where(BusinessLedgerEntry.entry_type.in_(entry_types))
        .order_by(BusinessLedgerEntry.effective_at.desc(), BusinessLedgerEntry.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if user_id is not None:
        stmt = stmt.where(BusinessLedgerEntry.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())
