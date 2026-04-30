from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.database.schemas.ai.message import AIMessageRead


class AIChatBase(BaseModel):
    user_id: int = Field(ge=1)
    conversation_id: str = Field(min_length=1)


class AIChatCreate(AIChatBase):
    pass


class AIChatUpdate(BaseModel):
    conversation_id: str | None = Field(default=None, min_length=1)


class AIChatRead(AIChatBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class AIChatWithMessagesRead(AIChatRead):
    messages: list[AIMessageRead] = Field(default_factory=list)
