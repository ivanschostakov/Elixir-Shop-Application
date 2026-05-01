from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.database.schemas.ai.attachment import AIAttachmentRead
from src.database.schemas.ai.interactive import AIInteractivePayload
from src.integrations.ai.enums import BotModel, MessageSender


class AIMessageUsageBase(BaseModel):
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    bot_model: BotModel
    openai_model: str = Field(min_length=1, max_length=120)


class AIMessageUsageCreate(AIMessageUsageBase):
    message_id: int = Field(ge=1)


class AIMessageUsageRead(AIMessageUsageBase):
    model_config = ConfigDict(from_attributes=True)

    message_id: int
    created_at: datetime
    updated_at: datetime


class AIMessageBase(BaseModel):
    user_id: int = Field(ge=1)
    chat_id: int = Field(ge=1)
    text: str = Field(min_length=1)
    sender: MessageSender


class AIMessageCreate(AIMessageBase):
    context_json: dict[str, Any] | None = None


class AIMessageUpdate(BaseModel):
    chat_id: int | None = Field(default=None, ge=1)
    text: str | None = Field(default=None, min_length=1)
    sender: MessageSender | None = None
    context_json: dict[str, Any] | None = None


class AIMessageRead(AIMessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    attachments: list[AIAttachmentRead] = Field(default_factory=list)
    interactive: AIInteractivePayload | None = None
    usage: AIMessageUsageRead | None = None
    created_at: datetime
    updated_at: datetime
