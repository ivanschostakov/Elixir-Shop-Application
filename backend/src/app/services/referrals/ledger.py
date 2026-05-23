from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.database.models import BusinessLedgerEntry
from .calculations import quantize_money

DEPOSIT_ENTRY_TYPES = {"website_bonus_seed", "referral_commission", "manual_adjustment", "deposit_spend"}


async def ledger_entry_exists(db: AsyncSession, idempotency_key: str) -> bool:
    return (await db.execute(select(BusinessLedgerEntry.id).where(BusinessLedgerEntry.idempotency_key == idempotency_key).limit(1))).scalar_one_or_none() is not None


async def create_ledger_entry_if_missing(db: AsyncSession, *, idempotency_key: str, user_id: int | None, amount: Decimal, currency: str, entry_type: str, direction: str, source_system: str, source_code: str | None = None, order_id: int | None = None, order_benefit_application_id: int | None = None, referral_commission_entry_id: int | None = None, website_identity_id: int | None = None, note: str | None = None, effective_at: datetime | None = None) -> BusinessLedgerEntry | None:
    if await ledger_entry_exists(db, idempotency_key): return None

    entry = BusinessLedgerEntry(
        order_id=order_id,
        order_benefit_application_id=order_benefit_application_id,
        referral_commission_entry_id=referral_commission_entry_id,
        user_id=user_id,
        website_identity_id=website_identity_id,
        entry_type=entry_type,
        direction=direction,
        amount=quantize_money(amount),
        currency=currency,
        source_system=source_system,
        source_code=source_code,
        status="posted",
        effective_at=effective_at or ufa_now(),
        note=note,
        idempotency_key=idempotency_key,
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_deposit_balance(db: AsyncSession, user_id: int) -> Decimal:
    rows = (await db.execute(select(BusinessLedgerEntry.direction, BusinessLedgerEntry.amount).where(BusinessLedgerEntry.user_id == user_id, BusinessLedgerEntry.status == "posted", BusinessLedgerEntry.entry_type.in_(DEPOSIT_ENTRY_TYPES)))).all()
    balance = Decimal("0.00")

    for direction, amount in rows:
        if direction == "credit": balance += quantize_money(amount)
        elif direction == "debit": balance -= quantize_money(amount)

    return max(Decimal("0.00"), quantize_money(balance))