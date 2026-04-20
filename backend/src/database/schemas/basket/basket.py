from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.database.schemas.basket.basket_item import BasketItemRead


class BasketBase(BaseModel):
    user_id: int = Field(ge=1)


class BasketCreate(BasketBase):
    pass


class BasketUpdate(BaseModel):
    user_id: int | None = Field(default=None, ge=1)


class BasketRead(BasketBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    items: list[BasketItemRead]
    items_count: int = Field(ge=0)
    total_quantity: int = Field(ge=0)
    total_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    has_unavailable_items: bool
    created_at: datetime
    updated_at: datetime
