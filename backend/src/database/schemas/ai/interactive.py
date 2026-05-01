from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AIActionType = Literal["open_product", "open_checkout", "ask_ai", "add_to_basket"]
AIActionStyle = Literal["primary", "secondary", "link"]
AIProductIntent = Literal["recommend", "compare", "alternative"]


class AIInteractiveAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    type: AIActionType
    label: str = Field(min_length=1, max_length=120)
    style: AIActionStyle = "secondary"
    product_id: int | None = Field(default=None, ge=1)
    variant_id: int | None = Field(default=None, ge=1)
    quantity: int | None = Field(default=None, ge=1, le=100)
    prompt: str | None = Field(default=None, max_length=500)
    action_token: str | None = None
    completed: bool = False
    created_basket_item_id: int | None = Field(default=None, ge=1)


class AIInteractiveVariant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    sku: str | None = None
    name: str
    stock: int = Field(ge=0)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    image_url: str
    in_stock: bool


class AIInteractiveActionRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_ids: list[str] = Field(default_factory=list, min_length=1, max_length=3)


class AIInteractiveProductCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    product_id: int = Field(ge=1)
    intent: AIProductIntent = "recommend"
    title: str = Field(min_length=1, max_length=500)
    reason: str | None = Field(default=None, max_length=500)
    image_url: str
    in_stock: bool
    variants: list[AIInteractiveVariant] = Field(default_factory=list, max_length=6)
    actions: list[AIInteractiveAction] = Field(default_factory=list, max_length=8)
    action_rows: list[AIInteractiveActionRow] = Field(default_factory=list, max_length=8)


class AIInteractivePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cards: list[AIInteractiveProductCard] = Field(default_factory=list, max_length=6)
