from pydantic import BaseModel, Field

from src.database.schemas import AIChatWithMessagesRead, BasketRead
from src.integrations.ai.enums import BotModel


class AIChatTurnMetaRead(BaseModel):
    selected_bot_model: BotModel
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    conversation_reset_reason: str | None = None


class AIChatResponse(BaseModel):
    chat: AIChatWithMessagesRead
    last_turn: AIChatTurnMetaRead | None = None
    basket: BasketRead | None = None


class AIChatActionPayload(BaseModel):
    message_id: int = Field(gt=0)
    action_id: str = Field(min_length=1, max_length=120)
    action_token: str = Field(min_length=1)
    quantity: int | None = Field(default=None, ge=1, le=100)


class AIChatActionResponse(AIChatResponse):
    basket_item_id: int | None = None


class AIChatTranscriptionResponse(BaseModel):
    text: str
