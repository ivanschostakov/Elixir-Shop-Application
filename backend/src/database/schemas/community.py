from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CommunityAccessState = Literal["granted", "telegram_link_required", "membership_required", "temporarily_unavailable"]
CommunityDeliveryStatus = Literal["queued", "sending", "sent", "failed", "delivery_unknown"]


class CommunityGroupRead(BaseModel):
    title: str
    image_url: str | None = None


class CommunityStatusRead(BaseModel):
    enabled: bool
    access: CommunityAccessState
    group: CommunityGroupRead | None = None
    action_url: str | None = None


class CommunityAuthorRead(BaseModel):
    id: int
    full_name: str
    avatar_url: str | None = None
    is_current_user: bool = False


class CommunityAttachmentRead(BaseModel):
    id: int
    kind: Literal["image", "document"]
    filename: str
    mime_type: str | None = None
    size_bytes: int
    media_url: str | None = None
    available_in_telegram: bool = False


class CommunityReplyPreviewRead(BaseModel):
    id: int
    author_name: str
    text: str


class CommunityMessageRead(BaseModel):
    id: int
    topic_id: int
    author: CommunityAuthorRead
    text: str
    attachments: list[CommunityAttachmentRead] = Field(default_factory=list)
    reply_to: CommunityReplyPreviewRead | None = None
    unsupported_type: str | None = None
    telegram_url: str | None = None
    delivery_status: CommunityDeliveryStatus
    created_at: datetime


class CommunityMessagePageRead(BaseModel):
    messages: list[CommunityMessageRead]
    has_more: bool = False
    oldest_id: int | None = None
    newest_id: int | None = None


class CommunityTopicRead(BaseModel):
    id: int
    name: str
    icon_color: int | None = None
    icon_custom_emoji_id: str | None = None
    is_closed: bool
    last_message: CommunityMessageRead | None = None
    unread_count: int = 0


class CommunityTopicListRead(BaseModel):
    topics: list[CommunityTopicRead]
    total_unread: int = 0


class CommunityMarkReadPayload(BaseModel):
    last_message_id: int = Field(ge=1)


class CommunityMarkReadResponse(BaseModel):
    ok: bool = True
