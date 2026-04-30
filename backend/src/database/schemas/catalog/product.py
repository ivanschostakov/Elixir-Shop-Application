import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.database.limits import (
    PRODUCT_DESCRIPTION_MAX_LENGTH,
    PRODUCT_EXPIRATION_MAX_LENGTH,
    PRODUCT_NAME_MAX_LENGTH,
    PRODUCT_SKU_MAX_LENGTH,
    PRODUCT_USAGE_MAX_LENGTH,
)
from src.database.product_text import normalize_product_text
from src.database.schemas.catalog.variant import ProductVariantRead


class ProductBase(BaseModel):
    sku: str = Field(min_length=1, max_length=PRODUCT_SKU_MAX_LENGTH)
    name: str = Field(min_length=1, max_length=PRODUCT_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=PRODUCT_DESCRIPTION_MAX_LENGTH)
    usage: str | None = Field(default=None, max_length=PRODUCT_USAGE_MAX_LENGTH)
    expiration: str | None = Field(default=None, max_length=PRODUCT_EXPIRATION_MAX_LENGTH)
    priority: int = Field(default=0, ge=0)

    @field_validator("description", "usage", "expiration", mode="before")
    @classmethod
    def normalize_rich_text(cls, value):
        return normalize_product_text(value)


class ProductCreate(ProductBase):
    system_id: uuid.UUID | None = None


class ProductUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=PRODUCT_SKU_MAX_LENGTH)
    name: str | None = Field(default=None, min_length=1, max_length=PRODUCT_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=PRODUCT_DESCRIPTION_MAX_LENGTH)
    usage: str | None = Field(default=None, max_length=PRODUCT_USAGE_MAX_LENGTH)
    expiration: str | None = Field(default=None, max_length=PRODUCT_EXPIRATION_MAX_LENGTH)
    priority: int | None = Field(default=None, ge=0)
    system_id: uuid.UUID | None = None

    @field_validator("description", "usage", "expiration", mode="before")
    @classmethod
    def normalize_rich_text(cls, value):
        return normalize_product_text(value)


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    system_id: uuid.UUID
    in_stock: bool
    image_url: str
    rating_avg: float = 0.0
    rating_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProductWithVariantsRead(ProductRead):
    variants: list[ProductVariantRead]
