from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, Field
from src.database.schemas.orders.order import OrderStatusCode
from .base import CustomerCompact


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


class AdminOrderOperationPayload(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=160)
    expected_updated_at: datetime
