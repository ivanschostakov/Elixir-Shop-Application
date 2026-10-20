from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, Field
from src.database.schemas.orders.order import OrderStatusCode


class AdminCustomerSegmentPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    filters_json: dict[str, Any] = Field(default_factory=dict)
    is_shared: bool = False
    segment_type: Literal["dynamic", "static"] = "dynamic"


class AdminCustomerSegmentUpdatePayload(AdminCustomerSegmentPayload):
    expected_updated_at: datetime


class AdminCustomerSegmentRead(AdminCustomerSegmentPayload):
    id: int
    owner_user_id: int
    owner_name: str
    audience_count: int
    push_reachable_count: int
    snapshot_version: int = 0
    snapshot_at: datetime | None = None
    snapshot_count: int = 0
    created_at: datetime
    updated_at: datetime


class AdminAudienceSample(BaseModel):
    id: int
    name: str
    surname: str
    email: str | None
    phone_number: str | None
    orders_count: int
    paid_total: Decimal
    last_order_at: datetime | None


class AdminAudiencePreview(BaseModel):
    count: int
    push_reachable_count: int
    sample: list[AdminAudienceSample]


class AdminCustomerSegmentSnapshotRead(BaseModel):
    segment_id: int
    snapshot_version: int
    snapshot_count: int
    snapshot_at: datetime


class AdminCustomerSegmentHistoryRead(BaseModel):
    id: int
    action: str
    actor_name: str | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    metadata_json: dict[str, Any]
    created_at: datetime


class AdminTaskCreatePayload(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_at: datetime | None = None
    customer_user_id: int | None = Field(default=None, ge=1)
    order_id: int | None = Field(default=None, ge=1)
    assignee_user_id: int | None = Field(default=None, ge=1)


class AdminTaskUpdatePayload(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    status: Literal["open", "in_progress", "done", "canceled"] | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    due_at: datetime | None = None
    customer_user_id: int | None = Field(default=None, ge=1)
    order_id: int | None = Field(default=None, ge=1)
    assignee_user_id: int | None = Field(default=None, ge=1)
    expected_updated_at: datetime


class AdminTaskRead(BaseModel):
    id: int
    title: str
    description: str | None
    status: str
    priority: str
    due_at: datetime | None
    completed_at: datetime | None
    sla_policy_id: int | None
    response_due_at: datetime | None
    resolution_due_at: datetime | None
    first_started_at: datetime | None
    sla_breached_at: datetime | None
    customer_user_id: int | None
    customer_name: str | None
    order_id: int | None
    order_code: str | None
    assignee_user_id: int
    assignee_name: str
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime


class AdminAssigneeOption(BaseModel):
    user_id: int
    name: str


class AdminPushCampaignPayload(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=180)
    body: str = Field(min_length=1, max_length=500)
    deep_link: str | None = Field(default=None, max_length=500)
    segment_id: int = Field(ge=1)
    template_id: int | None = Field(default=None, ge=1)
    goal: str | None = Field(default=None, max_length=120)
    utm_json: dict[str, Any] = Field(default_factory=dict)


class AdminPushCampaignUpdatePayload(AdminPushCampaignPayload):
    expected_updated_at: datetime


class AdminPushCampaignLaunchPayload(BaseModel):
    expected_updated_at: datetime
    expected_audience_count: int = Field(ge=1, le=50000)
    scheduled_at: datetime | None = None
    idempotency_key: str = Field(min_length=8, max_length=160)


class AdminPushCampaignControlPayload(BaseModel):
    expected_updated_at: datetime


class AdminPushCampaignRead(BaseModel):
    id: int
    name: str
    title: str
    body: str
    deep_link: str | None
    template_id: int | None
    template_name: str | None
    goal: str | None
    utm_json: dict[str, Any]
    status: str
    segment_id: int | None
    segment_name: str | None
    audience_count: int
    sent_count: int
    skipped_count: int
    failed_count: int
    opened_count: int
    clicked_count: int
    delivery_rate: Decimal
    click_rate: Decimal
    scheduled_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class AdminPushCampaignTemplateRead(BaseModel):
    id: int
    code: str
    category: str
    name_ru: str
    name_en: str
    title_ru: str
    title_en: str
    body_ru: str
    body_en: str
    deep_link: str | None
    goal: str | None
    is_active: bool


class AdminPushCampaignPreviewPayload(AdminPushCampaignPayload):
    locale: Literal["ru", "en"] = "ru"


class AdminPushCampaignPreviewRead(BaseModel):
    title: str
    body: str
    deep_link: str | None
    segment_id: int
    segment_name: str
    audience_count: int
    push_reachable_count: int
    estimated_send_count: int
    warnings: list[str]


class AdminPushCampaignRecipientRead(BaseModel):
    id: int
    user_id: int
    customer_name: str
    customer_email: str | None
    status: str
    attempts: int
    error: str | None
    sent_at: datetime | None
    opened_at: datetime | None
    clicked_at: datetime | None


class AdminPushCampaignMetricsRead(BaseModel):
    campaign_id: int
    audience_count: int
    sent_count: int
    skipped_count: int
    failed_count: int
    opened_count: int
    clicked_count: int
    pending_count: int
    delivery_rate: Decimal
    click_rate: Decimal
    failure_rate: Decimal


class AdminMarketingAutomationRead(BaseModel):
    id: int
    code: str
    name_ru: str
    name_en: str
    is_enabled: bool
    settings_json: dict[str, Any]
    last_run_at: datetime | None
    last_result_json: dict[str, Any]
    last_error: str | None
    updated_at: datetime


class AdminMarketingAutomationUpdatePayload(BaseModel):
    is_enabled: bool
    settings_json: dict[str, Any] = Field(default_factory=dict)
    expected_updated_at: datetime


class AdminOrderAutomationRulePayload(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    priority: int = Field(default=100, ge=1, le=1000)
    conditions_json: dict[str, Any]
    action_json: dict[str, Any]
    is_enabled: bool = False


class AdminOrderAutomationRuleUpdatePayload(AdminOrderAutomationRulePayload):
    expected_updated_at: datetime


class AdminOrderAutomationRuleRead(AdminOrderAutomationRulePayload):
    id: int
    created_by_name: str | None
    last_run_at: datetime | None
    last_match_count: int
    last_error: str | None
    executions_count: int
    created_at: datetime
    updated_at: datetime


class AdminOrderAutomationExecutionRead(BaseModel):
    id: int
    rule_id: int
    order_id: int
    order_code: str
    action_kind: str
    status: str
    result_json: dict[str, Any]
    error: str | None
    executed_at: datetime


class AdminOrderAutomationPreviewItem(BaseModel):
    order_id: int
    order_code: str
    status_code: OrderStatusCode
    payment_status: str
    customer_name: str
    created_at: datetime


class AdminOrderAutomationPreviewRead(BaseModel):
    matched: int
    sample: list[AdminOrderAutomationPreviewItem]


class AdminOrderAutomationPresetRead(BaseModel):
    code: str
    name_ru: str
    name_en: str
    description_ru: str
    description_en: str
    priority: int
    conditions_json: dict[str, Any]
    action_json: dict[str, Any]
    exists: bool
    rule_id: int | None = None


class AdminOrderAutomationPresetApplyResponse(BaseModel):
    created: int
    skipped: int
    items: list[AdminOrderAutomationPresetRead]


class AdminAutomationRunResponse(BaseModel):
    matched: int
    executed: int
    skipped: int
    failed: int


class AdminAutomationRunPayload(BaseModel):
    expected_updated_at: datetime
    idempotency_key: str = Field(min_length=8, max_length=160)
