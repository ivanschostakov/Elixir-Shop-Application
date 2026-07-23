from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AdminReferralProfileRead(BaseModel):
    id: int = Field(ge=1)
    user_id: int = Field(ge=1)
    total_purchases: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    referral_discount_base_total: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    current_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    created_at: datetime
    updated_at: datetime


class AdminReferralSummaryRead(BaseModel):
    profiles_count: int = Field(ge=0)
    active_referrers_count: int = Field(ge=0)
    total_discount_base: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    average_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    max_discount_percent: Decimal = Field(ge=0, max_digits=7, decimal_places=2)
    discount_bands: list[dict[str, int]]
