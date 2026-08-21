from datetime import datetime
from typing import Any, Literal

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


class AdminAIChatSecuritySourceSummary(BaseModel):
    source: Literal["app", "bitrix"]
    configured: bool = True
    window_hours: int = 24
    events: int = 0
    messages: int = 0
    suspicious: int = 0
    active_bans: int = 0
    error: str | None = None


class AdminAIChatSecurityOverview(BaseModel):
    app: AdminAIChatSecuritySourceSummary
    bitrix: AdminAIChatSecuritySourceSummary


class AdminAIChatSecurityEventRead(BaseModel):
    id: int
    source: Literal["app", "bitrix"]
    event_type: str
    outcome: str
    account_id: str
    email_address: str | None
    display_name: str | None
    ip_address: str | None
    session_id: int | None = None
    message_id: int | None = None
    risk_score: int
    is_suspicious: bool
    risk_reasons: list[str]
    details: dict[str, Any]
    created_at: datetime


class AdminAIChatSecurityEventPage(BaseModel):
    items: list[AdminAIChatSecurityEventRead]
    total: int
    limit: int
    offset: int


class AdminAIChatBanRead(BaseModel):
    id: int
    source: Literal["app", "bitrix"]
    ban_type: Literal["account", "ip"]
    subject: str
    reason: str
    is_active: bool
    created_by: str | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminAIChatBanPage(BaseModel):
    items: list[AdminAIChatBanRead]
    total: int
    limit: int
    offset: int


class AdminAIChatBanCreate(BaseModel):
    source: Literal["app", "bitrix"]
    ban_type: Literal["account", "ip"]
    subject: str
    reason: str
    expires_at: datetime | None = None
