from pydantic import Field, BaseModel, ConfigDict
from typing import Literal
from src.app.services.ai.chat_interactive import ProductRequestedAction, ProductRefIntent


class StructuredProductRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    variant_id: int | None = Field(default=None, gt=0)
    intent: ProductRefIntent = "recommend"
    reason: str = Field(min_length=1, max_length=500)
    requested_actions: list[ProductRequestedAction] = Field(default_factory=list, max_length=4)
    button_rows: list[list[str]] = Field(default_factory=list, max_length=6)


class StructuredBasketItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=100)


class StructuredBasketAddition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[StructuredBasketItem] = Field(default_factory=list, min_length=1, max_length=10)


class StructuredAIChatOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assistant_text: str = Field(min_length=1, max_length=12000)
    product_refs: list[StructuredProductRef] = Field(default_factory=list, max_length=6)
    basket_addition: StructuredBasketAddition | None = None


class AIActionTokenPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v: Literal[1] = 1
    user_id: int = Field(gt=0)
    chat_id: int = Field(gt=0)
    message_id: int = Field(gt=0)
    action_id: str = Field(min_length=1, max_length=120)
    expires_at: int = Field(gt=0)
