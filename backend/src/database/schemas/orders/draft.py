from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import (
    CURRENCY_CODE_MAX_LENGTH,
    ORDER_DRAFT_COMMENT_MAX_LENGTH,
    ORDER_DRAFT_NAME_MAX_LENGTH,
    PRODUCT_NAME_MAX_LENGTH,
    PRODUCT_SKU_MAX_LENGTH,
    STATUS_MAX_LENGTH,
    VARIANT_NAME_MAX_LENGTH,
    VARIANT_SKU_MAX_LENGTH,
)
from src.database.schemas.delivery.address import DeliveryAddressRead
from src.database.schemas.delivery.recipient import DeliveryRecipientRead


class OrderDraftItemBase(BaseModel):
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


class OrderDraftItemCreate(OrderDraftItemBase):
    draft_id: int = Field(ge=1)


class OrderDraftItemRead(OrderDraftItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    draft_id: int
    image_url: str
    created_at: datetime
    updated_at: datetime


class OrderDraftBase(BaseModel):
    user_id: int = Field(ge=1)
    delivery_address_id: int | None = Field(default=None, ge=1)
    recipient_id: int | None = Field(default=None, ge=1)
    status: str = Field(min_length=1, max_length=STATUS_MAX_LENGTH)
    items_count: int = Field(ge=0)
    total_quantity: int = Field(ge=0)
    basket_subtotal: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    delivery_total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    grand_total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=1, max_length=CURRENCY_CODE_MAX_LENGTH)
    delivery_period_min: int | None = Field(default=None, ge=0)
    delivery_period_max: int | None = Field(default=None, ge=0)
    draft_name: str | None = Field(default=None, max_length=ORDER_DRAFT_NAME_MAX_LENGTH)
    comment: str | None = Field(default=None, max_length=ORDER_DRAFT_COMMENT_MAX_LENGTH)


class OrderDraftCreate(OrderDraftBase):
    pass


class OrderDraftUpdate(BaseModel):
    draft_name: str | None = Field(default=None, max_length=ORDER_DRAFT_NAME_MAX_LENGTH)
    comment: str | None = Field(default=None, max_length=ORDER_DRAFT_COMMENT_MAX_LENGTH)
    delivery_address_id: int | None = Field(default=None, ge=1)
    recipient_id: int | None = Field(default=None, ge=1)
    items_count: int | None = Field(default=None, ge=0)
    total_quantity: int | None = Field(default=None, ge=0)
    basket_subtotal: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    delivery_total: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    grand_total: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, max_length=CURRENCY_CODE_MAX_LENGTH)
    delivery_period_min: int | None = Field(default=None, ge=0)
    delivery_period_max: int | None = Field(default=None, ge=0)


class OrderDraftCheckoutOptionsRead(BaseModel):
    addresses: list[DeliveryAddressRead]
    recipients: list[DeliveryRecipientRead]


class OrderDraftRead(OrderDraftBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    delivery_address: DeliveryAddressRead | None
    recipient: DeliveryRecipientRead | None
    items: list[OrderDraftItemRead]
    created_at: datetime
    updated_at: datetime
