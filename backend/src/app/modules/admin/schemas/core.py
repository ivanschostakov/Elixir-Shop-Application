from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.database.schemas.orders.order import OrderStatusCode

T = TypeVar("T")


class AdminPage(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class DashboardMetrics(BaseModel):
    revenue: Decimal
    paid_orders: int
    average_order_value: Decimal
    new_customers: int
    failed_payments: int
    pending_reviews: int
    low_stock_variants: int
    abandoned_baskets: int
    integration_errors: int
    overdue_tasks: int
    sla_breached_tasks: int
    sla_compliance_percent: Decimal


class DashboardTrendPoint(BaseModel):
    day: date
    revenue: Decimal
    orders: int


class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    revenue_trend: list[DashboardTrendPoint]


class AdminAnalyticsResponse(BaseModel):
    days: int
    generated_at: datetime
    sales: dict[str, Any]
    customers: dict[str, Any]
    products: dict[str, Any]
    discounts: dict[str, Any]
    marketing: dict[str, Any]


class CustomerCompact(BaseModel):
    id: int
    name: str
    surname: str
    email: EmailStr | None = None
    phone_number: str | None = None


class AdminOrderListItem(BaseModel):
    id: int
    order_code: str
    status: str
    status_code: OrderStatusCode
    customer: CustomerCompact
    items_count: int
    total_quantity: int
    grand_total: Decimal
    currency: str
    payment_method: str | None
    payment_status: str
    delivery_service: str
    is_paid: bool
    is_canceled: bool
    amocrm_lead_id: int | None
    created_at: datetime
    updated_at: datetime


class AdminOrderItemRead(BaseModel):
    id: int
    product_id: int
    variant_id: int
    product_name: str
    product_sku: str
    variant_name: str
    variant_sku: str | None
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class AdminOrderDetail(AdminOrderListItem):
    basket_subtotal: Decimal
    delivery_total: Decimal
    comment: str | None
    delivery_string: str | None
    delivery_period_min: int | None
    delivery_period_max: int | None
    payment_provider: str | None
    payment_invoice_id: str | None
    payment_paid_at: datetime | None
    payment_error: str | None
    delivery_created_at: datetime | None
    delivery_provider_ref: str | None
    yandex_request_id: str | None
    moysklad_customerorder_id: str | None
    moysklad_invoiceout_id: str | None
    recipient: dict[str, Any]
    address: dict[str, Any]
    items: list[AdminOrderItemRead]
    benefits: dict[str, Any]


class AdminOrderTransitionPayload(BaseModel):
    status_code: OrderStatusCode
    expected_updated_at: datetime
    idempotency_key: str = Field(min_length=8, max_length=160)
    reason: str | None = Field(default=None, max_length=1000)


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


class CustomerStatusPayload(BaseModel):
    is_active: bool
    expected_updated_at: datetime


class AdminVariantRead(BaseModel):
    id: int
    system_id: str
    sku: str | None
    name: str
    stock: int
    price: Decimal
    archived: bool


class AdminProductRead(BaseModel):
    id: int
    system_id: str
    sku: str
    name: str
    description: str | None
    usage: str | None
    expiration: str | None
    in_stock: bool
    archived: bool
    priority: int
    image_url: str
    category_ids: list[int]
    variants: list[AdminVariantRead]
    updated_at: datetime


class AdminProductMerchandisePayload(BaseModel):
    description: str | None = None
    usage: str | None = None
    expiration: str | None = None
    priority: int = Field(ge=0)
    category_ids: list[int] = Field(default_factory=list)
    expected_updated_at: datetime


class AdminCategoryPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    archived: bool = False


class AdminCategoryRead(AdminCategoryPayload):
    id: int
    created_at: datetime
    updated_at: datetime


class AdminReviewRead(BaseModel):
    id: int
    product_id: int
    product_name: str
    user_id: int | None
    author_name: str
    author_email: str | None
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


class IntegrationStatusRead(BaseModel):
    provider: str
    label: str
    configured: bool
    status: Literal["healthy", "warning", "error", "disabled"]
    last_run_at: datetime | None
    last_run_status: str | None
    last_error: str | None


class IntegrationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    operation: str
    status: str
    target_type: str | None
    target_id: str | None
    retry_of_id: int | None
    attempts: int
    max_attempts: int
    counters_json: dict[str, Any]
    error: str | None
    started_at: datetime
    heartbeat_at: datetime | None
    next_attempt_at: datetime | None
    finished_at: datetime | None


class IntegrationRetryPayload(BaseModel):
    operation: Literal["catalog_sync"]
    idempotency_key: str = Field(min_length=8, max_length=160)


class IntegrationRunRetryPayload(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=160)


class AdminOrderOperationPayload(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=160)
    expected_updated_at: datetime


class IntegrationQueueHealthRead(BaseModel):
    queue_available: bool
    queue_depth: int
    processing_depth: int
    scheduled_depth: int
    queued: int
    running: int
    retrying: int
    failed_24h: int
    stale_running: int
    oldest_pending_at: datetime | None


class AdminExportCreatePayload(BaseModel):
    resource: Literal["orders", "customers", "products", "reviews", "audit"]
    format: Literal["csv", "xlsx"]
    columns: list[str] = Field(min_length=1, max_length=32)
    filters: dict[str, Any] = Field(default_factory=dict)
    selected_ids: list[int] = Field(default_factory=list, max_length=5000)
    locale: Literal["ru", "en"] = "ru"
    idempotency_key: str = Field(min_length=8, max_length=160)


class AdminExportRead(BaseModel):
    id: int
    resource: str
    format: str
    status: str
    rows: int | None
    file_name: str | None
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class AuditLogRead(BaseModel):
    id: int
    actor_name: str
    action: str
    entity_type: str
    entity_id: str | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    context_json: dict[str, Any]
    ip_address: str | None
    request_id: str | None
    created_at: datetime


class SearchResultItem(BaseModel):
    type: Literal["order", "customer", "product"]
    id: int
    title: str
    subtitle: str
    path: str


class SearchResponse(BaseModel):
    items: list[SearchResultItem]


class SavedViewPayload(BaseModel):
    resource: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    state_json: dict[str, Any]
    is_shared: bool = False


class SavedViewRead(SavedViewPayload):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    created_at: datetime
    updated_at: datetime


class StaffRead(BaseModel):
    user_id: int
    email: str | None
    name: str
    surname: str
    is_active: bool
    mfa_enabled: bool
    last_login_at: datetime | None
    role_codes: list[str]


class StaffRolesPayload(BaseModel):
    role_codes: list[str] = Field(min_length=1)
    confirm_superadmin: bool = False


class StaffCreatePayload(StaffRolesPayload):
    email: EmailStr


class StaffStatusPayload(BaseModel):
    is_active: bool


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


class AdminSlaPolicyRead(BaseModel):
    id: int
    priority: str
    name_ru: str
    name_en: str
    response_minutes: int
    resolution_minutes: int
    is_enabled: bool
    updated_at: datetime


class AdminSlaPolicyUpdatePayload(BaseModel):
    response_minutes: int = Field(ge=5, le=10080)
    resolution_minutes: int = Field(ge=15, le=43200)
    is_enabled: bool
    expected_updated_at: datetime


class AdminSlaSummaryItem(BaseModel):
    assignee_user_id: int
    assignee_name: str
    open_tasks: int
    breached_tasks: int
    completed_30d: int
    on_time_30d: int
    compliance_percent: Decimal


class AdminAlertRead(BaseModel):
    id: int
    severity: str
    source: str
    code: str
    title_ru: str
    title_en: str
    message: str
    entity_type: str | None
    entity_id: str | None
    path: str | None
    occurrence_count: int
    is_read: bool
    last_occurred_at: datetime
    resolved_at: datetime | None
    created_at: datetime


class AdminAlertPage(BaseModel):
    items: list[AdminAlertRead]
    unread_count: int
    total: int


class AdminDashboardPreferenceRead(BaseModel):
    widgets: list[str]
    updated_at: datetime | None


class AdminDashboardPreferencePayload(BaseModel):
    widgets: list[str] = Field(min_length=1, max_length=16)
    expected_updated_at: datetime | None = None


class AdminReadinessCheck(BaseModel):
    key: str
    label_ru: str
    label_en: str
    status: Literal["ok", "warning", "error", "unknown"]
    message_ru: str
    message_en: str
    details: dict[str, Any] = Field(default_factory=dict)


class AdminWorkerHeartbeatRead(BaseModel):
    name: str
    status: Literal["ok", "warning", "unknown"]
    last_seen_at: datetime | None
    stale_after_seconds: int


class AdminProductionReadinessRead(BaseModel):
    overall_status: Literal["ok", "warning", "error", "unknown"]
    generated_at: datetime
    public_host: str | None
    checklist_summary: dict[str, int] = Field(default_factory=dict)
    checks: list[AdminReadinessCheck]
    workers: list[AdminWorkerHeartbeatRead]
