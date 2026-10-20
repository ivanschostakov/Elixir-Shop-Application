from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, Field


class AdminReviewRead(BaseModel):
    id: int
    product_id: int
    product_name: str
    user_id: int | None
    author_name: str
    author_email: str | None
    hide_sender_name: bool = False
    value: int
    text: str | None
    answer: str | None
    status: Literal["pending", "published", "rejected"]
    attachments: list[str]
    attachment_items: list[dict[str, Any]] = Field(default_factory=list)
    spam_score: int
    profanity_flag: bool
    duplicate_flag: bool
    suspicious_ip_flag: bool
    moderation_flags: dict[str, Any]
    internal_moderation_comment: str | None = None
    submitter_ip: str | None = None
    appeal_status: str
    moderated_at: datetime | None = None
    restored_at: datetime | None = None
    customer_notified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminReviewModerationPayload(BaseModel):
    action: Literal["publish", "reject", "restore"]
    answer: str | None = Field(default=None, max_length=4000)
    internal_comment: str | None = Field(default=None, max_length=4000)
    attachment_statuses: dict[int, Literal["approved", "rejected", "pending"]] = Field(default_factory=dict)
    expected_updated_at: datetime


class AdminProductQuestionRead(BaseModel):
    id: int
    product_id: int
    product_name: str
    user_id: int | None
    author_name: str
    author_email: str | None
    text: str
    answer: str | None
    status: Literal["pending", "published", "rejected"]
    internal_moderation_comment: str | None = None
    moderated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminProductQuestionModerationPayload(BaseModel):
    action: Literal["publish", "reject"]
    answer: str | None = Field(default=None, max_length=4000)
    internal_comment: str | None = Field(default=None, max_length=4000)
    expected_updated_at: datetime


class AdminReviewBulkModerationItem(BaseModel):
    id: int = Field(ge=1)
    expected_updated_at: datetime


class AdminReviewBulkModerationPayload(BaseModel):
    action: Literal["publish", "reject"]
    items: list[AdminReviewBulkModerationItem] = Field(min_length=1, max_length=200)
    internal_comment: str | None = Field(default=None, max_length=4000)


class AdminReviewModerationEventRead(BaseModel):
    id: int
    action: str
    actor_name: str | None
    comment: str | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    metadata_json: dict[str, Any]
    created_at: datetime


class AdminBannerPayload(BaseModel):
    image_path: str | None = Field(default=None, max_length=500)
    desktop_image_path: str | None = Field(default=None, max_length=500)
    mobile_image_path: str | None = Field(default=None, max_length=500)
    title: str | None = Field(default=None, max_length=240)
    inner_link: str | None = Field(default=None, max_length=500)
    outer_link: str | None = Field(default=None, max_length=500)
    priority: int = Field(default=0, ge=0)
    archived: bool = False
    status: Literal["draft", "scheduled", "published", "archived"] = "draft"
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    audience_json: dict[str, Any] = Field(default_factory=dict)


class AdminBannerRead(AdminBannerPayload):
    id: int
    image_path: str
    click_count: int
    impression_count: int
    created_at: datetime
    updated_at: datetime


class AdminBannerUpdatePayload(AdminBannerPayload):
    expected_updated_at: datetime


class AdminBannerUploadRead(BaseModel):
    image_path: str
    url: str


class AdminBannerDailyStatRead(BaseModel):
    day: date
    impressions: int
    clicks: int
    ctr_percent: Decimal


class AdminBannerStatsRead(BaseModel):
    banner_id: int
    impressions: int
    clicks: int
    ctr_percent: Decimal
    daily: list[AdminBannerDailyStatRead]


class AdminBusinessContentPayload(BaseModel):
    title_ru: str = Field(min_length=1, max_length=240)
    title_en: str = Field(min_length=1, max_length=240)
    body_ru: str = Field(default="", max_length=50000)
    body_en: str = Field(default="", max_length=50000)
    link_url: str | None = Field(default=None, max_length=2048)
    status: Literal["draft", "published", "archived"] = "draft"
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AdminBusinessContentUpdatePayload(AdminBusinessContentPayload):
    expected_updated_at: datetime


class AdminBusinessContentRead(AdminBusinessContentPayload):
    id: int
    code: str
    version: int
    updated_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminBusinessContentVersionRead(BaseModel):
    id: int
    version: int
    actor_name: str | None
    snapshot_json: dict[str, Any]
    created_at: datetime
