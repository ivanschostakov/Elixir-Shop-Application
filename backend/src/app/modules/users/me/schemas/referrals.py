from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import PROMO_CODE_MAX_LENGTH, STATUS_MAX_LENGTH


class ReferralProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(ge=1)
    total_purchases: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    referral_discount_base_total: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    current_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    bonus_points: int = Field(default=0, ge=0)
    bonus_rubles: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    bonus_program_name: str | None = None
    bonus_spend_rate_points_to_ruble: int = Field(default=1, ge=1)
    bonus_max_paid_rate_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, max_digits=7, decimal_places=2)
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
