from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ConversationStatus = Literal["new", "open", "waiting_customer", "waiting_team", "resolved", "spam"]
ConversationPriority = Literal["low", "normal", "high", "urgent"]


class AdminSupportAttachmentRead(BaseModel):
    id: int
    original_filename: str
    mime_type: str
    size_bytes: int
    download_url: str


class AdminSupportMessageRead(BaseModel):
    id: int
    sender_type: Literal["user", "admin", "system"]
    body: str
    author_user_id: int | None
    author_name: str
    author_role: str | None
    is_internal: bool
    delivered_at: datetime | None
    read_at: datetime | None
    attachments: list[AdminSupportAttachmentRead]
    created_at: datetime
    updated_at: datetime


class AdminSupportConversationRead(BaseModel):
    id: int
    customer_user_id: int
    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    subject: str | None
    status: ConversationStatus
    priority: ConversationPriority
    assignee_user_id: int | None
    assignee_name: str | None
    order_id: int | None
    order_code: str | None
    response_due_at: datetime | None
    resolution_due_at: datetime | None
    first_responded_at: datetime | None
    resolved_at: datetime | None
    last_message_at: datetime | None
    sla_breached_at: datetime | None
    admin_unread_count: int
    customer_unread_count: int
    last_message_preview: str | None
    created_at: datetime
    updated_at: datetime


class AdminSupportConversationDetail(AdminSupportConversationRead):
    messages: list[AdminSupportMessageRead]


class AdminSupportMessagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=8000)
    is_internal: bool = False


class AdminSupportConversationUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_updated_at: datetime
    status: ConversationStatus | None = None
    priority: ConversationPriority | None = None
    assignee_user_id: int | None = None
    order_id: int | None = None
    subject: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def has_change(self):
        changed_fields = self.model_fields_set - {"expected_updated_at"}
        if not changed_fields:
            raise ValueError("At least one conversation field must be changed")
        return self


class AdminSupportReadResponse(BaseModel):
    conversation_id: int
    unread_count: int
