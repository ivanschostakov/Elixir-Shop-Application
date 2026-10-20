from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class DashboardMetrics(BaseModel):
    revenue: Decimal
    paid_orders: int
    average_order_value: Decimal
    new_customers: int
    online_customers: int
    online_window_minutes: int
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
