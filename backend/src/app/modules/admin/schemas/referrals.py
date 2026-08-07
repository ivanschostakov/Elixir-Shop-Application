from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdminReferralProfileRead(BaseModel):
    id: int = Field(ge=1)
    user_id: int = Field(ge=1)
    reward_program: Literal["bonus", "partner"]
    reward_program_selected_at: datetime | None = None
    reward_program_selection_source: str | None = Field(default=None, max_length=32)
    bitrix_user_id: int | None = Field(default=None, ge=1)
    bitrix_sync_status: str = Field(max_length=32)
    bitrix_synced_at: datetime | None = None
    partner_unlocked_at: datetime | None = None
    partner_program_status: Literal["locked", "active"]
    total_purchases: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    referral_discount_base_total: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    current_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    created_at: datetime
    updated_at: datetime

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
    wallet_sync_status: str = Field(max_length=32)
    bonus_points_credited: int | None = Field(default=None, ge=0)
    bonus_rubles_credited: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    wallet_synced_at: datetime | None = None
    wallet_sync_error: str | None = Field(default=None, max_length=500)
    settlement_method: Literal["deposit", "transfer"]
    settlement_reference: str | None = Field(default=None, max_length=255)
    settled_at: datetime | None = None
    settled_by_admin_user_id: int | None = Field(default=None, ge=1)
    wallet_reversed_at: datetime | None = None
    bitrix_sync_status: str
    paid_at: datetime
    created_at: datetime
    updated_at: datetime


class AdminRewardProgramUpdatePayload(BaseModel):
    program: Literal["bonus", "partner"]
    reason: str = Field(min_length=1, max_length=500)


class AdminOpeningBalanceUpdatePayload(BaseModel):
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="RUB", min_length=3, max_length=3)


class AdminReferralTransferPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    beneficiary_bitrix_user_id: int = Field(ge=1)
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    reference: str = Field(min_length=1, max_length=255)


class AdminReferralSettlementRead(BaseModel):
    beneficiary_user_id: int | None = Field(default=None, ge=1)
    beneficiary_bitrix_user_id: int = Field(ge=1)
    beneficiary_email: str | None = None
    beneficiary_name: str | None = None
    period: str
    currency: str
    accruals_count: int = Field(ge=0)
    approved_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    deposited_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    transferred_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    awaiting_deposit_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    awaiting_settlement_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class AdminReferralTransferResult(BaseModel):
    beneficiary_bitrix_user_id: int = Field(ge=1)
    period: str
    currency: str
    reference: str
    accruals_count: int = Field(ge=1)
    transferred_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    settled_at: datetime
