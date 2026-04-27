from typing import Literal

from pydantic import BaseModel, Field

RecommendationSurface = Literal["home", "product", "cart", "draft"]


class RecommendationViewPayload(BaseModel):
    product_id: int = Field(ge=1)
    variant_id: int | None = Field(default=None, ge=1)


class RecommendationCategoryViewPayload(BaseModel):
    category_id: int = Field(ge=1)
