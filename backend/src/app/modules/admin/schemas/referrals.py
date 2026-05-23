from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.database.limits import CURRENCY_CODE_MAX_LENGTH, LEDGER_NOTE_MAX_LENGTH, PROMO_CODE_MAX_LENGTH, SOURCE_KIND_MAX_LENGTH, STATUS_MAX_LENGTH


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


class AdminReferralProfileRead(BaseModel):
    id: int = Field(ge=1)
    user_id: int = Field(ge=1)
    website_identity_id: int | None = Field(default=None, ge=1)
    initial_purchase_balance: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    website_seed_purchase_balance: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    app_paid_purchase_total: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    total_purchases: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    current_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    referrer_promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    referrer_user_id: int | None = Field(default=None, ge=1)
    own_promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    deposit_balance: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    created_at: datetime
    updated_at: datetime


class ManualDepositAdjustmentRead(BaseModel):
    entry_id: int = Field(ge=1)
    balance: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class AdminReferralPromoCodeRead(BaseModel):
    id: int = Field(ge=1)
    code: str = Field(min_length=1, max_length=PROMO_CODE_MAX_LENGTH)
    owner_user_id: int = Field(ge=1)
    is_active: bool
    source_system: str = Field(max_length=SOURCE_KIND_MAX_LENGTH)
    issued_at: datetime
    created_at: datetime


class AdminReferralCommissionRead(BaseModel):
    id: int = Field(ge=1)
    period_start: date
    period_end: date
    order_id: int = Field(ge=1)
    buyer_user_id: int | None = Field(default=None, ge=1)
    referrer_user_id: int | None = Field(default=None, ge=1)
    level: int = Field(ge=1)
    promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    commission_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    commission_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(max_length=CURRENCY_CODE_MAX_LENGTH)
    status: str = Field(max_length=STATUS_MAX_LENGTH)
    posted_at: datetime | None = None


class AdminReferralDepositRead(BaseModel):
    id: int = Field(ge=1)
    user_id: int | None = Field(default=None, ge=1)
    entry_type: str = Field(max_length=SOURCE_KIND_MAX_LENGTH)
    direction: str = Field(max_length=SOURCE_KIND_MAX_LENGTH)
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    currency: str = Field(max_length=CURRENCY_CODE_MAX_LENGTH)
    source_system: str = Field(max_length=SOURCE_KIND_MAX_LENGTH)
    source_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    status: str = Field(max_length=STATUS_MAX_LENGTH)
    note: str | None = Field(default=None, max_length=LEDGER_NOTE_MAX_LENGTH)
    effective_at: datetime


class CommissionRunRead(BaseModel):
    dry_run: bool
    count: int = Field(ge=0)
    entries: list[dict[str, Any]] = Field(default_factory=list)
