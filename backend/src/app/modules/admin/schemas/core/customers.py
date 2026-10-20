from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, Field
from .base import CustomerCompact


class CustomerListItem(CustomerCompact):
    is_active: bool
    is_verified: bool
    telegram_username: str | None
    orders_count: int
    paid_total: Decimal
    last_order_at: datetime | None
    last_active_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminNoteRead(BaseModel):
    id: int
    body: str
    author_name: str
    created_at: datetime
    updated_at: datetime


class AdminNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class CustomerMarketingProfileRead(BaseModel):
    lifecycle_stage: str
    lead_score: int
    engagement_score: int
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    last_event_name: str | None
    last_platform: str | None
    last_app_version: str | None
    push_permission: str
    preferred_language: str | None
    timezone: str | None
    sessions_count: int
    total_events: int
    product_views: int
    category_views: int
    searches_count: int
    banner_clicks: int
    push_opens: int
    push_clicks: int
    cart_adds: int
    cart_removes: int
    checkout_started: int
    checkout_failed: int
    orders_created: int
    orders_paid: int
    last_purchase_at: datetime | None
    updated_at: datetime


class CustomerDeviceRead(BaseModel):
    id: int
    installation_id: str
    platform: str
    app_version: str | None
    app_build: str | None
    os_version: str | None
    device_model: str | None
    language: str | None
    timezone: str | None
    push_permission: str
    install_source: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    sessions_count: int
    is_active: bool


class CustomerEventRead(BaseModel):
    id: int
    event_id: str
    event_name: str
    source: str
    session_id: str | None
    device_id: int | None
    entity_type: str | None
    entity_id: int | None
    occurred_at: datetime
    received_at: datetime
    properties: dict[str, Any]
    attribution: dict[str, Any]


class CustomerConsentRead(BaseModel):
    id: int
    purpose: str
    channel: str
    is_granted: bool
    source: str
    policy_version: str | None
    granted_at: datetime | None
    revoked_at: datetime | None
    last_changed_at: datetime


class CustomerAttributionRead(BaseModel):
    first_source: str | None
    first_medium: str | None
    first_campaign: str | None
    first_content: str | None
    first_term: str | None
    first_referrer: str | None
    first_landing_page: str | None
    first_touch_at: datetime | None
    last_source: str | None
    last_medium: str | None
    last_campaign: str | None
    last_content: str | None
    last_term: str | None
    last_referrer: str | None
    last_landing_page: str | None
    last_touch_at: datetime | None
    install_source: str | None


class CustomerDetail(CustomerListItem):
    contact_id: int | None
    moysklad_counterparty_id: str | None
    promo_code: str | None
    basket_items: int
    basket_total: Decimal
    favourites_count: int
    push_tokens_count: int
    push_delivery_status: Literal["ready", "no_token", "permission_denied", "unknown"]
    push_reachable: bool
    last_push_token_at: datetime | None
    last_push_dispatch_at: datetime | None
    referral_discount_base_total: Decimal
    referral_discount_percent: Decimal
    total_product_views: int
    total_cart_quantity: int
    marketing_profile: CustomerMarketingProfileRead | None
    devices: list[CustomerDeviceRead]
    recent_events: list[CustomerEventRead]
    consents: list[CustomerConsentRead]
    attribution: CustomerAttributionRead | None
    notes: list[AdminNoteRead]


class CustomerPushTestRead(BaseModel):
    accepted: bool
    status: Literal["accepted", "no_token", "rejected"]
    sent_at: datetime | None


class CustomerDeletePayload(BaseModel):
    confirmation: Literal["DELETE"]
    expected_updated_at: datetime


class CustomerStatusPayload(BaseModel):
    is_active: bool
    expected_updated_at: datetime
