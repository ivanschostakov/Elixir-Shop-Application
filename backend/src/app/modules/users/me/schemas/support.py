from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


SupportConversationStatus = Literal["new", "open", "waiting_customer", "waiting_team", "resolved", "spam"]
SupportMessageSender = Literal["user", "admin", "system"]


class SupportAttachmentRead(BaseModel):
    id: int
    original_filename: str
    mime_type: str
    size_bytes: int
    download_url: str


class SupportMessageRead(BaseModel):
    id: int
    sender_type: SupportMessageSender
    body: str
    author_name: str
    author_role: str | None = None
    is_internal: bool
    delivered_at: datetime | None
    read_at: datetime | None
    attachments: list[SupportAttachmentRead]
    created_at: datetime
    updated_at: datetime


class SupportConversationSummaryRead(BaseModel):
    id: int
    subject: str | None
    status: SupportConversationStatus
    priority: Literal["low", "normal", "high", "urgent"]
    assignee_name: str | None
    customer_unread_count: int
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SupportConversationRead(SupportConversationSummaryRead):
    messages: list[SupportMessageRead]


class SupportInboxRead(BaseModel):
    active: SupportConversationRead | None
    previous: list[SupportConversationSummaryRead]
    total_unread: int


class SupportConversationCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_message_id: UUID
    subject: str | None = Field(default=None, max_length=240)
    message: str = Field(min_length=1, max_length=8000)


class SupportMessageCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_message_id: UUID
    message: str = Field(default="", max_length=8000)


class SupportReadResponse(BaseModel):
    conversation_id: int
    unread_count: int
