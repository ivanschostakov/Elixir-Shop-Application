import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import VARIANT_NAME_MAX_LENGTH, VARIANT_SKU_MAX_LENGTH


class VariantBase(BaseModel):
    product_id: int = Field(ge=1)
    sku: str | None = Field(default=None, min_length=1, max_length=VARIANT_SKU_MAX_LENGTH)
    name: str = Field(min_length=1, max_length=VARIANT_NAME_MAX_LENGTH)
    stock: int = Field(default=0, ge=0)
    archived: bool = False
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class VariantCreate(VariantBase):
    system_id: uuid.UUID | None = None


class VariantUpdate(BaseModel):
    product_id: int | None = Field(default=None, ge=1)
    sku: str | None = Field(default=None, min_length=1, max_length=VARIANT_SKU_MAX_LENGTH)
    name: str | None = Field(default=None, min_length=1, max_length=VARIANT_NAME_MAX_LENGTH)
    stock: int | None = Field(default=None, ge=0)
    archived: bool | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    system_id: uuid.UUID | None = None


class VariantRead(VariantBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    system_id: uuid.UUID
    image_url: str
    created_at: datetime
    updated_at: datetime


class ProductVariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    system_id: uuid.UUID
    image_url: str
    sku: str | None
    name: str
    stock: int
    archived: bool
    price: Decimal
    original_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    discounted_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    discount_percent: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=7, decimal_places=2)
    created_at: datetime
    updated_at: datetime
