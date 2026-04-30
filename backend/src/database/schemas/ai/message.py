from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.database.schemas.ai.attachment import AIAttachmentRead
from src.integrations.ai.enums import BotModel, MessageSender


class AIMessageBase(BaseModel):
    user_id: int = Field(ge=1)
    chat_id: int = Field(ge=1)
    text: str = Field(min_length=1)
    sender: MessageSender
    bot_model: BotModel


class AIMessageCreate(AIMessageBase):
    pass


class AIMessageUpdate(BaseModel):
    chat_id: int | None = Field(default=None, ge=1)
    text: str | None = Field(default=None, min_length=1)
    sender: MessageSender | None = None
    bot_model: BotModel | None = None


class AIMessageRead(AIMessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    attachments: list[AIAttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
