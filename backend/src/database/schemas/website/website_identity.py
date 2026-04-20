from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from config import ufa_now

from src.database.limits import (
    BUSINESS_NAME_MAX_LENGTH,
    CURRENCY_CODE_MAX_LENGTH,
    LEDGER_NOTE_MAX_LENGTH,
    PROMO_CODE_MAX_LENGTH,
    SOURCE_KIND_MAX_LENGTH,
    STATUS_MAX_LENGTH,
    WEBSITE_CITY_MAX_LENGTH,
    WEBSITE_EMAIL_MAX_LENGTH,
    WEBSITE_LOGIN_MAX_LENGTH,
    WEBSITE_PHONE_MAX_LENGTH,
)


class WebsiteReferralProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    website_identity_id: int
    own_promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    referrer_website_user_id: int | None = None
    referrer_promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    referral_percent: float | None = None
    referral_turnover_amount: float | None = None
    referral_turnover_currency: str | None = Field(default=None, max_length=CURRENCY_CODE_MAX_LENGTH)
    monthly_paid_orders_amount: float | None = None
    monthly_paid_orders_currency: str | None = Field(default=None, max_length=CURRENCY_CODE_MAX_LENGTH)
    tier_group_id: int | None = None
    tier_group_name: str | None = Field(default=None, max_length=BUSINESS_NAME_MAX_LENGTH)
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebsiteBonusAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    website_identity_id: int
    website_bonus_account_external_id: int | None = None
    is_active: bool
    balance: float
    currency: str | None = Field(default=None, max_length=CURRENCY_CODE_MAX_LENGTH)
    website_created_at: datetime | None = None
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebsiteDiscountEntitlementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    website_identity_id: int
    source_kind: str = Field(max_length=SOURCE_KIND_MAX_LENGTH)
    website_source_id: str | None = None
    source_name: str = Field(max_length=BUSINESS_NAME_MAX_LENGTH)
    discount_percent: float | None = None
    discount_amount: float | None = None
    currency: str | None = Field(default=None, max_length=CURRENCY_CODE_MAX_LENGTH)
    priority: int | None = None
    is_stackable: bool
    is_active: bool
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebsiteCouponRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    website_identity_id: int
    website_coupon_external_id: int | None = None
    coupon_code: str = Field(max_length=PROMO_CODE_MAX_LENGTH)
    discount_rule_id: int | None = None
    discount_rule_name: str | None = Field(default=None, max_length=BUSINESS_NAME_MAX_LENGTH)
    discount_type: str | None = Field(default=None, max_length=SOURCE_KIND_MAX_LENGTH)
    discount_value: float | None = None
    discount_currency: str | None = Field(default=None, max_length=CURRENCY_CODE_MAX_LENGTH)
    max_use: int | None = None
    use_count: int
    is_active: bool
    description: str | None = Field(default=None, max_length=LEDGER_NOTE_MAX_LENGTH)
    website_created_at: datetime | None = None
    website_applied_at: datetime | None = None
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebsiteIdentityBase(BaseModel):
    user_id: int = Field(gt=0)
    website_user_id: int = Field(gt=0)
    website_login: str = Field(min_length=1, max_length=WEBSITE_LOGIN_MAX_LENGTH)
    website_email: str | None = Field(default=None, max_length=WEBSITE_EMAIL_MAX_LENGTH)
    website_name: str | None = Field(default=None, max_length=WEBSITE_LOGIN_MAX_LENGTH)
    website_last_name: str | None = Field(default=None, max_length=WEBSITE_LOGIN_MAX_LENGTH)
    website_second_name: str | None = Field(default=None, max_length=WEBSITE_LOGIN_MAX_LENGTH)
    website_phone: str | None = Field(default=None, max_length=WEBSITE_PHONE_MAX_LENGTH)
    website_mobile: str | None = Field(default=None, max_length=WEBSITE_PHONE_MAX_LENGTH)
    website_city: str | None = Field(default=None, max_length=WEBSITE_CITY_MAX_LENGTH)
    website_registered_at: datetime | None = None
    website_last_login_at: datetime | None = None
    group_ids: list[int] = Field(default_factory=list)
    group_names: list[str] = Field(default_factory=list)
    custom_fields: dict[str, str] = Field(default_factory=dict)
    referral_program: dict[str, Any] | None = None
    bonus_account: dict[str, Any] | None = None
    discount_groups: list[dict[str, Any]] = Field(default_factory=list)
    active_coupons: list[dict[str, Any]] = Field(default_factory=list)
    recent_used_coupons: list[dict[str, Any]] = Field(default_factory=list)
    raw_payload: dict[str, Any] | None = None
    last_synced_at: datetime | None = None


class WebsiteIdentityCreate(WebsiteIdentityBase):
    last_synced_at: datetime = Field(default_factory=ufa_now)


class WebsiteIdentityUpdate(BaseModel):
    website_user_id: int | None = Field(default=None, gt=0)
    website_login: str | None = Field(default=None, min_length=1, max_length=WEBSITE_LOGIN_MAX_LENGTH)
    website_email: str | None = Field(default=None, max_length=WEBSITE_EMAIL_MAX_LENGTH)
    website_name: str | None = Field(default=None, max_length=WEBSITE_LOGIN_MAX_LENGTH)
    website_last_name: str | None = Field(default=None, max_length=WEBSITE_LOGIN_MAX_LENGTH)
    website_second_name: str | None = Field(default=None, max_length=WEBSITE_LOGIN_MAX_LENGTH)
    website_phone: str | None = Field(default=None, max_length=WEBSITE_PHONE_MAX_LENGTH)
    website_mobile: str | None = Field(default=None, max_length=WEBSITE_PHONE_MAX_LENGTH)
    website_city: str | None = Field(default=None, max_length=WEBSITE_CITY_MAX_LENGTH)
    website_registered_at: datetime | None = None
    website_last_login_at: datetime | None = None
    group_ids: list[int] | None = None
    group_names: list[str] | None = None
    custom_fields: dict[str, str] | None = None
    referral_program: dict[str, Any] | None = None
    bonus_account: dict[str, Any] | None = None
    discount_groups: list[dict[str, Any]] | None = None
    active_coupons: list[dict[str, Any]] | None = None
    recent_used_coupons: list[dict[str, Any]] | None = None
    raw_payload: dict[str, Any] | None = None
    last_synced_at: datetime | None = None


class WebsiteIdentityRead(WebsiteIdentityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    referral_profile: WebsiteReferralProfileRead | None = None
    bonus_account_snapshot: WebsiteBonusAccountRead | None = None
    discount_entitlements: list[WebsiteDiscountEntitlementRead] = Field(default_factory=list)
    coupon_snapshots: list[WebsiteCouponRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
