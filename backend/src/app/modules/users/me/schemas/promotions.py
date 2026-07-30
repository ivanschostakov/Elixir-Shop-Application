from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from src.database.limits import PRODUCT_CATEGORY_NAME_MAX_LENGTH, PRODUCT_NAME_MAX_LENGTH


class ProfilePromotionRead(BaseModel):
    kind: Literal["product", "category"]
    title: str = Field(min_length=1, max_length=PRODUCT_NAME_MAX_LENGTH)
    subtitle: str | None = None
    discount_percent: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    image_url: str
    product_id: int = Field(ge=1)
    product_name: str = Field(min_length=1, max_length=PRODUCT_NAME_MAX_LENGTH)
    category_id: int | None = Field(default=None, ge=1)
    category_name: str | None = Field(default=None, max_length=PRODUCT_CATEGORY_NAME_MAX_LENGTH)
