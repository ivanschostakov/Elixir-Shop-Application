from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AdminAIChatListItem(BaseModel):
    id: int
    user_id: int
    customer_name: str
    customer_email: str | None
    messages_count: int
    user_messages_count: int
    total_tokens: int
    last_message: str | None
    last_activity_at: datetime
    created_at: datetime


class AdminAIChatMessageRead(BaseModel):
    id: int
    sender: str
    text: str
    context: dict[str, Any]
    attachments: list[dict[str, Any]]
    usage: dict[str, Any] | None
    created_at: datetime


class AdminAIChatActionRead(BaseModel):
    id: int
    event_name: str
    source: str
    message_id: int | None
    action_id: str | None
    action_type: str | None
    product_id: int | None
    variant_id: int | None
    basket_item_id: int | None
    properties: dict[str, Any]
    occurred_at: datetime


class AdminAIChatDetail(BaseModel):
    id: int
    user_id: int
    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    conversation_id: str
    current_tokens: int
    total_tokens: int
    messages: list[AdminAIChatMessageRead]
    actions: list[AdminAIChatActionRead]
    created_at: datetime
    updated_at: datetime
