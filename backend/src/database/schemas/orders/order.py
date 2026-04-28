from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import (
    CURRENCY_CODE_MAX_LENGTH,
    EXTERNAL_ID_MAX_LENGTH,
    ORDER_CODE_MAX_LENGTH,
    ORDER_DELIVERY_STRING_MAX_LENGTH,
    ORDER_DRAFT_COMMENT_MAX_LENGTH,
    PAYMENT_METHOD_MAX_LENGTH,
    PAYMENT_PROVIDER_MAX_LENGTH,
    PAYMENT_STATUS_MAX_LENGTH,
    PRODUCT_NAME_MAX_LENGTH,
    PRODUCT_SKU_MAX_LENGTH,
    STATUS_MAX_LENGTH,
    VARIANT_NAME_MAX_LENGTH,
    VARIANT_SKU_MAX_LENGTH,
)
from src.database.schemas.delivery.address import DeliveryAddressRead
from src.database.schemas.delivery.recipient import DeliveryRecipientRead

OrderHistoryBucket = Literal["active", "completed"]
OrderStatusCode = Literal[
    "created",
    "invoice_sent",
    "paid",
    "waiting_response",
    "packaged",
    "sent",
    "delivered",
    "canceled",
    "completed",
    "refund_declined",
]


class OrderItemBase(BaseModel):
    user_id: int = Field(ge=1)
    product_id: int = Field(ge=1)
    variant_id: int = Field(ge=1)
    product_name: str = Field(min_length=1, max_length=PRODUCT_NAME_MAX_LENGTH)
    product_sku: str = Field(min_length=1, max_length=PRODUCT_SKU_MAX_LENGTH)
    variant_name: str = Field(min_length=1, max_length=VARIANT_NAME_MAX_LENGTH)
    variant_sku: str | None = Field(default=None, max_length=VARIANT_SKU_MAX_LENGTH)
    quantity: int = Field(ge=1)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    line_total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class OrderItemCreate(OrderItemBase):
    order_id: int = Field(ge=1)


class OrderItemRead(OrderItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    image_url: str
    created_at: datetime
    updated_at: datetime


class OrderBase(BaseModel):
    draft_id: int | None = Field(default=None, ge=1)
    user_id: int = Field(ge=1)
    delivery_address_id: int = Field(ge=1)
    recipient_id: int = Field(ge=1)
    order_code: str = Field(min_length=1, max_length=ORDER_CODE_MAX_LENGTH)
    status: str = Field(min_length=1, max_length=STATUS_MAX_LENGTH)
    items_count: int = Field(ge=0)
    total_quantity: int = Field(ge=0)
    basket_subtotal: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    delivery_total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    grand_total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=1, max_length=CURRENCY_CODE_MAX_LENGTH)
    delivery_period_min: int | None = Field(default=None, ge=0)
    delivery_period_max: int | None = Field(default=None, ge=0)
    comment: str | None = Field(default=None, max_length=ORDER_DRAFT_COMMENT_MAX_LENGTH)
    delivery_string: str | None = Field(default=None, max_length=ORDER_DELIVERY_STRING_MAX_LENGTH)
    selected_delivery_service: str = Field(min_length=1, max_length=STATUS_MAX_LENGTH)
    selected_delivery_payload: dict[str, Any] = Field(default_factory=dict)
    checkout_snapshot: dict[str, Any] = Field(default_factory=dict)
    payment_method: str | None = Field(default=None, max_length=PAYMENT_METHOD_MAX_LENGTH)
    payment_provider: str | None = Field(default=None, max_length=PAYMENT_PROVIDER_MAX_LENGTH)
    payment_status: str = Field(min_length=1, max_length=PAYMENT_STATUS_MAX_LENGTH)
    payment_invoice_id: str | None = Field(default=None, max_length=EXTERNAL_ID_MAX_LENGTH)
    payment_paid_at: datetime | None = None
    payment_error: str | None = Field(default=None, max_length=ORDER_DRAFT_COMMENT_MAX_LENGTH)
    amocrm_lead_id: int | None = Field(default=None, ge=1)
    delivery_created_at: datetime | None = None
    delivery_provider_ref: str | None = Field(default=None, max_length=EXTERNAL_ID_MAX_LENGTH)
    yandex_request_id: str | None = Field(default=None, max_length=EXTERNAL_ID_MAX_LENGTH)
    is_active: bool
    is_paid: bool
    is_canceled: bool
    is_shipped: bool


class OrderCreate(OrderBase):
    pass


class OrderUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=STATUS_MAX_LENGTH)
    items_count: int | None = Field(default=None, ge=0)
    total_quantity: int | None = Field(default=None, ge=0)
    basket_subtotal: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    delivery_total: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    grand_total: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, max_length=CURRENCY_CODE_MAX_LENGTH)
    delivery_period_min: int | None = Field(default=None, ge=0)
    delivery_period_max: int | None = Field(default=None, ge=0)
    comment: str | None = Field(default=None, max_length=ORDER_DRAFT_COMMENT_MAX_LENGTH)
    delivery_string: str | None = Field(default=None, max_length=ORDER_DELIVERY_STRING_MAX_LENGTH)
    selected_delivery_service: str | None = Field(default=None, max_length=STATUS_MAX_LENGTH)
    selected_delivery_payload: dict[str, Any] | None = None
    checkout_snapshot: dict[str, Any] | None = None
    payment_method: str | None = Field(default=None, max_length=PAYMENT_METHOD_MAX_LENGTH)
    payment_provider: str | None = Field(default=None, max_length=PAYMENT_PROVIDER_MAX_LENGTH)
    payment_status: str | None = Field(default=None, max_length=PAYMENT_STATUS_MAX_LENGTH)
    payment_invoice_id: str | None = Field(default=None, max_length=EXTERNAL_ID_MAX_LENGTH)
    payment_paid_at: datetime | None = None
    payment_error: str | None = Field(default=None, max_length=ORDER_DRAFT_COMMENT_MAX_LENGTH)
    amocrm_lead_id: int | None = Field(default=None, ge=1)
    delivery_created_at: datetime | None = None
    delivery_provider_ref: str | None = Field(default=None, max_length=EXTERNAL_ID_MAX_LENGTH)
    yandex_request_id: str | None = Field(default=None, max_length=EXTERNAL_ID_MAX_LENGTH)
    is_active: bool | None = None
    is_paid: bool | None = None
    is_canceled: bool | None = None
    is_shipped: bool | None = None


class OrderRead(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    status_code: OrderStatusCode
    history_bucket: OrderHistoryBucket
    delivery_address: DeliveryAddressRead
    recipient: DeliveryRecipientRead
    items: list[OrderItemRead]
    created_at: datetime
    updated_at: datetime
