from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import PRODUCT_CATEGORY_DESCRIPTION_MAX_LENGTH, PRODUCT_CATEGORY_NAME_MAX_LENGTH


class ProductCategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=PRODUCT_CATEGORY_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=PRODUCT_CATEGORY_DESCRIPTION_MAX_LENGTH)
    archived: bool = False
    discount_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, max_digits=5, decimal_places=2)


class ProductCategoryCreate(ProductCategoryBase):
    pass


class ProductCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=PRODUCT_CATEGORY_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=PRODUCT_CATEGORY_DESCRIPTION_MAX_LENGTH)
    archived: bool | None = None
    discount_percent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)


class ProductCategoryRead(ProductCategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
