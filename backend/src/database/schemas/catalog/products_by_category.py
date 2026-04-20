from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductByCategoryBase(BaseModel):
    product_id: int = Field(ge=1)
    category_id: int = Field(ge=1)


class ProductByCategoryCreate(ProductByCategoryBase):
    pass


class ProductByCategoryUpdate(BaseModel):
    product_id: int | None = Field(default=None, ge=1)
    category_id: int | None = Field(default=None, ge=1)


class ProductByCategoryRead(ProductByCategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
