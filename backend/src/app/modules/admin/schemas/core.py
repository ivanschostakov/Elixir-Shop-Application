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


class DashboardTrendPoint(BaseModel):
    day: date
    revenue: Decimal
    orders: int


class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    revenue_trend: list[DashboardTrendPoint]


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
    created_at: datetime
    updated_at: datetime


class AdminReviewModerationPayload(BaseModel):
    action: Literal["publish", "reject"]
    answer: str | None = Field(default=None, max_length=4000)
    expected_updated_at: datetime


class AdminBannerPayload(BaseModel):
    image_path: str = Field(min_length=1, max_length=500)
    inner_link: str | None = Field(default=None, max_length=500)
    outer_link: str | None = Field(default=None, max_length=500)
    priority: int = Field(default=0, ge=0)
    archived: bool = False


class AdminBannerRead(AdminBannerPayload):
    id: int
    created_at: datetime
    updated_at: datetime


class AdminBannerUpdatePayload(AdminBannerPayload):
    expected_updated_at: datetime


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
    attempts: int
    counters_json: dict[str, Any]
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class IntegrationRetryPayload(BaseModel):
    operation: Literal["catalog_sync"]
    idempotency_key: str = Field(min_length=8, max_length=160)


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


class StaffCreatePayload(StaffRolesPayload):
    email: EmailStr


class StaffStatusPayload(BaseModel):
    is_active: bool
