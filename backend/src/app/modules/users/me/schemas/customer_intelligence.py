from datetime import datetime, timedelta, timezone
import json
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CustomerEventName = Literal[
    "app_opened",
    "product_viewed",
    "category_viewed",
    "search_submitted",
    "banner_clicked",
    "push_opened",
    "push_clicked",
    "cart_item_added",
    "cart_item_removed",
    "checkout_started",
    "checkout_failed",
    "order_created",
    "order_paid",
    "ai_chat_message_sent",
    "ai_recommendation_shown",
    "ai_action_clicked",
    "ai_action_completed",
]
EventSource = Literal["app", "api", "worker", "webhook", "admin"]
DevicePlatform = Literal["ios", "android", "web"]
PushPermission = Literal["granted", "denied", "undetermined", "provisional", "unknown"]
ConsentPurpose = Literal["analytics", "marketing", "personalization"]
ConsentChannel = Literal["all", "push", "email", "telegram"]


class CustomerAttributionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str | None = Field(default=None, max_length=128)
    medium: str | None = Field(default=None, max_length=128)
    campaign: str | None = Field(default=None, max_length=160)
    content: str | None = Field(default=None, max_length=160)
    term: str | None = Field(default=None, max_length=160)
    referrer: str | None = Field(default=None, max_length=500)
    landing_page: str | None = Field(default=None, max_length=500)
    install_source: str | None = Field(default=None, max_length=128)

    @field_validator("*", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        return value.strip() or None


class UserDeviceSyncPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    installation_id: str = Field(min_length=8, max_length=128)
    platform: DevicePlatform
    app_version: str | None = Field(default=None, max_length=32)
    app_build: str | None = Field(default=None, max_length=32)
    os_version: str | None = Field(default=None, max_length=64)
    device_model: str | None = Field(default=None, max_length=128)
    language: str | None = Field(default=None, max_length=16)
    timezone: str | None = Field(default=None, max_length=64)
    push_permission: PushPermission = "unknown"
    install_source: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "installation_id",
        "app_version",
        "app_build",
        "os_version",
        "device_model",
        "language",
        "timezone",
        "install_source",
        mode="before",
    )
    @classmethod
    def normalize_device_strings(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        return value.strip() or None

    @field_validator("metadata")
    @classmethod
    def limit_metadata_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")) > 4096:
            raise ValueError("Device metadata must not exceed 4 KB")
        return value


class CustomerConsentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: ConsentPurpose
    channel: ConsentChannel = "all"
    is_granted: bool
    source: EventSource = "app"
    policy_version: str | None = Field(default=None, max_length=32)
    changed_at: datetime | None = None


class CustomerEventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID
    name: CustomerEventName
    occurred_at: datetime
    session_id: str | None = Field(default=None, min_length=8, max_length=128)
    source: EventSource = "app"
    entity_type: str | None = Field(default=None, max_length=32)
    entity_id: int | None = Field(default=None, ge=1)
    properties: dict[str, Any] = Field(default_factory=dict)
    attribution: CustomerAttributionPayload | None = None

    @field_validator("occurred_at")
    @classmethod
    def validate_event_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        normalized = value.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if normalized < now - timedelta(days=90):
            raise ValueError("occurred_at is outside the 90-day ingestion window")
        if normalized > now + timedelta(minutes=10):
            raise ValueError("occurred_at cannot be more than 10 minutes in the future")
        return normalized

    @field_validator("properties")
    @classmethod
    def limit_properties_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")) > 8192:
            raise ValueError("Event properties must not exceed 8 KB")
        return value

    @model_validator(mode="after")
    def validate_entity_pair(self) -> "CustomerEventPayload":
        if (self.entity_type is None) != (self.entity_id is None):
            raise ValueError("entity_type and entity_id must be provided together")
        return self


class CustomerIntelligenceSyncPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device: UserDeviceSyncPayload | None = None
    consents: list[CustomerConsentPayload] = Field(default_factory=list, max_length=10)
    events: list[CustomerEventPayload] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_sync_payload(self) -> "CustomerIntelligenceSyncPayload":
        if self.device is None and not self.consents and not self.events:
            raise ValueError("At least one device, consent or event update is required")
        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("Duplicate event_id values in the same batch")
        consent_keys = [(consent.purpose, consent.channel) for consent in self.consents]
        if len(consent_keys) != len(set(consent_keys)):
            raise ValueError("Duplicate consent purpose/channel values in the same batch")
        return self


class CustomerIntelligenceSyncResponse(BaseModel):
    device_id: int | None
    accepted_events: int
    duplicate_events: int
    updated_consents: int
    profile_updated_at: datetime


__all__ = [
    "CustomerAttributionPayload",
    "CustomerConsentPayload",
    "CustomerEventName",
    "CustomerEventPayload",
    "CustomerIntelligenceSyncPayload",
    "CustomerIntelligenceSyncResponse",
    "UserDeviceSyncPayload",
]
