from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import PROMO_CODE_MAX_LENGTH, STATUS_MAX_LENGTH


class ReferralProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(ge=1)
    reward_program: Literal["combined"] = "combined"
    reward_program_selected_at: datetime | None = None
    reward_program_selection_source: str | None = Field(default=None, max_length=32)
    program_selection_required: bool = False
    bonus_program_enabled: bool = False
    partner_program_unlocked: bool = False
    partner_program_status: Literal["locked", "eligible", "active"] = "locked"
    partner_unlock_threshold: Decimal = Field(
        default=Decimal("100000.00"),
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    partner_unlock_remaining: Decimal = Field(
        default=Decimal("100000.00"),
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    personal_discount_next_threshold: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    personal_discount_remaining: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    bitrix_profile_found: bool = False
    bitrix_sync_status: str = Field(default="pending", max_length=32)
    bitrix_synced_at: datetime | None = None
    bitrix_user_id: int | None = Field(default=None, ge=1)
    total_purchases: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    referral_discount_base_total: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    current_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    own_promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    suggested_promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    referrer_promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    bonus_points: int = Field(default=0, ge=0)
    bonus_rubles: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    bonus_wallet_available: bool = False
    bonus_program_name: str | None = None
    bonus_spend_rate_points_to_ruble: int = Field(default=1, ge=1)
    bonus_max_paid_rate_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, max_digits=7, decimal_places=2)
    partner_pending_rubles: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    partner_approved_rubles: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    partner_rejected_rubles: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    partner_site_balance_rubles: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    partner_network_period: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    partner_network_status: str | None = Field(default=None, max_length=STATUS_MAX_LENGTH)
    partner_network_turnover: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    partner_network_rate_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, max_digits=7, decimal_places=2)
    partner_network_amount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    created_at: datetime
    updated_at: datetime


class RewardProgramSelectPayload(BaseModel):
    program: Literal["bonus", "partner", "combined"]


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
