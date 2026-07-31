from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import (
    BUSINESS_NAME_MAX_LENGTH,
    CURRENCY_CODE_MAX_LENGTH,
    PROMO_CODE_MAX_LENGTH,
    SOURCE_KIND_MAX_LENGTH,
    STATUS_MAX_LENGTH,
)


class BenefitCheckPayload(BaseModel):
    code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    subtotal: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    discountable_subtotal: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, max_length=CURRENCY_CODE_MAX_LENGTH)
    use_bonus_rubles: bool = False


class BenefitOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_kind: str = Field(max_length=SOURCE_KIND_MAX_LENGTH)
    source_record_id: int | None = Field(default=None, ge=1)
    code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    title: str = Field(max_length=BUSINESS_NAME_MAX_LENGTH)
    status: str = Field(max_length=STATUS_MAX_LENGTH)
    is_applicable: bool
    is_personal: bool = False
    is_stackable: bool = False
    calculation_mode: str = Field(max_length=SOURCE_KIND_MAX_LENGTH)
    discount_percent: Decimal | None = Field(default=None, ge=0, max_digits=7, decimal_places=2)
    discount_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, max_length=CURRENCY_CODE_MAX_LENGTH)
    estimated_discount_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    estimated_total_after: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    reason: str | None = None
    source_external_id: str | None = Field(default=None, max_length=128)
    benefit_units: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    benefit_unit_name: str | None = Field(default=None, max_length=SOURCE_KIND_MAX_LENGTH)
    sequence: int | None = Field(default=None, ge=1)
    applied_discount_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    subtotal_before: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    subtotal_after: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class BenefitCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    referral_profile_id: int | None = Field(default=None, ge=1)
    reward_program: Literal["combined"] = "combined"
    program_selection_required: bool = False
    subtotal_source: str = Field(max_length=SOURCE_KIND_MAX_LENGTH)
    basket_subtotal: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, max_length=CURRENCY_CODE_MAX_LENGTH)
    entered_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    entered_code_matches: list[BenefitOptionRead] = Field(default_factory=list)
    unresolved_code_reason: str | None = None
    available_discount_options: list[BenefitOptionRead] = Field(default_factory=list)
    personal_discount: BenefitOptionRead | None = None
    best_discount: BenefitOptionRead | None = None
    stacked_discount_options: list[BenefitOptionRead] = Field(default_factory=list)
    stacked_discount_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    total_after_discounts: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    bonus_option: BenefitOptionRead | None = None
    bonus_balance_points: int = Field(default=0, ge=0)
    bonus_balance_rubles: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    bonus_program_name: str | None = Field(default=None, max_length=BUSINESS_NAME_MAX_LENGTH)
    bonus_max_paid_rate_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, max_digits=7, decimal_places=2)
    use_bonus_rubles: bool = False
    bonus_applied_points: int = Field(default=0, ge=0)
    bonus_applied_rubles: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
