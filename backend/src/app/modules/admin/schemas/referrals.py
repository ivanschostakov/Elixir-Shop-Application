from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class AdminReferralProfileRead(BaseModel):
    id: int = Field(ge=1)
    user_id: int = Field(ge=1)
    reward_program: Literal["bonus", "partner"] | None = None
    reward_program_selected_at: datetime | None = None
    reward_program_selection_source: str | None = Field(default=None, max_length=32)
    total_purchases: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    referral_discount_base_total: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    current_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    created_at: datetime
    updated_at: datetime


class AdminRewardProgramChangePayload(BaseModel):
    program: Literal["bonus", "partner"]
    reason: str = Field(min_length=3, max_length=500)


class AdminRewardProgramChangeRead(BaseModel):
    user_id: int = Field(ge=1)
    reward_program: Literal["bonus", "partner"]
    reward_program_selected_at: datetime
    reward_program_selection_source: str


class AdminReferralDiscountBandRead(BaseModel):
    band: str
    count: int = Field(ge=0)


class AdminReferralSummaryRead(BaseModel):
    profiles_count: int = Field(ge=0)
    active_referrers_count: int = Field(ge=0)
    total_discount_base: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    average_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    max_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    discount_bands: list[AdminReferralDiscountBandRead]
    accruals_count: int = Field(ge=0)
    pending_accrual_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    approved_accrual_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    rejected_accrual_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class AdminReferralAccrualRead(BaseModel):
    id: int = Field(ge=1)
    purchase_id: int = Field(ge=1)
    order_id: int = Field(ge=1)
    external_order_id: str
    buyer_user_id: int | None = Field(default=None, ge=1)
    beneficiary_user_id: int | None = Field(default=None, ge=1)
    beneficiary_bitrix_user_id: int = Field(ge=1)
    beneficiary_email: str | None
    beneficiary_name: str | None
    promo_code: str | None
    period: str
    level: int = Field(ge=1, le=2)
    buyer_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    referrer_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    commission_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    order_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    commission_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str
    status: str
    reason: str | None
    bitrix_sync_status: str
    paid_at: datetime
    created_at: datetime
    updated_at: datetime
