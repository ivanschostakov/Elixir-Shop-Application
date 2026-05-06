from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import PRODUCT_CATEGORY_DESCRIPTION_MAX_LENGTH, PRODUCT_CATEGORY_NAME_MAX_LENGTH


class ProductCategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=PRODUCT_CATEGORY_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=PRODUCT_CATEGORY_DESCRIPTION_MAX_LENGTH)
    archived: bool = False


class ProductCategoryCreate(ProductCategoryBase):
    pass


class ProductCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=PRODUCT_CATEGORY_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=PRODUCT_CATEGORY_DESCRIPTION_MAX_LENGTH)
    archived: bool | None = None


class ProductCategoryRead(ProductCategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
