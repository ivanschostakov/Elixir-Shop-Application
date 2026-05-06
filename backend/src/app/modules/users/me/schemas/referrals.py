from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import CURRENCY_CODE_MAX_LENGTH, PROMO_CODE_MAX_LENGTH, SOURCE_KIND_MAX_LENGTH, STATUS_MAX_LENGTH


class ReferralProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(ge=1)
    total_purchases: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    initial_purchase_balance: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    website_seed_purchase_balance: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    app_paid_purchase_total: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    current_month_purchases: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    previous_month_purchases: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    current_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    referrer_promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    own_promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    accrued_commissions: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    deposit_balance: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    website_seed_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ReferrerCodeCheckPayload(BaseModel):
    code: str = Field(min_length=1, max_length=PROMO_CODE_MAX_LENGTH)


class ReferrerCodeCheckRead(BaseModel):
    code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    is_valid: bool
    status: str = Field(max_length=STATUS_MAX_LENGTH)
    reason: str | None = None
    warning: str | None = None
    requires_confirmation: bool = False
    referrer_user_id: int | None = Field(default=None, ge=1)
    depth: int | None = Field(default=None, ge=1)


class ReferrerCodeAttachPayload(ReferrerCodeCheckPayload):
    confirmed: bool = False


class DepositLedgerEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(ge=1)
    entry_type: str = Field(max_length=SOURCE_KIND_MAX_LENGTH)
    direction: str = Field(max_length=SOURCE_KIND_MAX_LENGTH)
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    currency: str = Field(max_length=CURRENCY_CODE_MAX_LENGTH)
    source_system: str = Field(max_length=SOURCE_KIND_MAX_LENGTH)
    source_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    status: str = Field(max_length=STATUS_MAX_LENGTH)
    note: str | None = None
    effective_at: datetime
    created_at: datetime


class DepositRead(BaseModel):
    balance: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(max_length=CURRENCY_CODE_MAX_LENGTH)
    ledger_entries: list[DepositLedgerEntryRead] = Field(default_factory=list)
