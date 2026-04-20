from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BasketItemBase(BaseModel):
    variant_id: int = Field(ge=1)
    quantity: int = Field(ge=1)


class BasketItemCreate(BasketItemBase):
    pass


class BasketItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


class BasketProductSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    in_stock: bool
    image_url: str


class BasketVariantSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str | None
    name: str
    stock: int
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    image_url: str


class BasketItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int = Field(ge=1)
    quantity: int = Field(ge=1)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    line_total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    available_quantity: int = Field(ge=0)
    is_available: bool
    product: BasketProductSummaryRead
    variant: BasketVariantSummaryRead
    created_at: datetime
    updated_at: datetime
