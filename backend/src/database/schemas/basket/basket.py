from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.database.schemas.basket.basket_item import BasketItemRead
from src.database.schemas.delivery.address import DeliveryAddressRead
from src.database.schemas.delivery.recipient import DeliveryRecipientRead


class BasketBase(BaseModel):
    user_id: int = Field(ge=1)


class BasketCreate(BasketBase):
    pass


class BasketUpdate(BaseModel):
    user_id: int | None = Field(default=None, ge=1)
    delivery_address_id: int | None = Field(default=None, ge=1)
    recipient_id: int | None = Field(default=None, ge=1)
    delivery_total: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = None
    delivery_period_min: int | None = Field(default=None, ge=0)
    delivery_period_max: int | None = Field(default=None, ge=0)


class BasketRead(BasketBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    items: list[BasketItemRead]
    delivery_address_id: int | None = None
    recipient_id: int | None = None
    delivery_address: DeliveryAddressRead | None = None
    recipient: DeliveryRecipientRead | None = None
    items_count: int = Field(ge=0)
    total_quantity: int = Field(ge=0)
    total_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    delivery_total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    grand_total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str
    delivery_period_min: int | None = None
    delivery_period_max: int | None = None
    has_unavailable_items: bool
    created_at: datetime
    updated_at: datetime
