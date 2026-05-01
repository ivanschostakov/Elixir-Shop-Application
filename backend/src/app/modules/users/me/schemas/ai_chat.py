from pydantic import BaseModel, Field

from src.database.schemas import AIChatWithMessagesRead
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


class AIChatTranscriptionResponse(BaseModel):
    text: str
