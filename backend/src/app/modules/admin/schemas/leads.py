from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


LeadStatus = Literal["new", "contacted", "interested", "waiting", "converted", "lost"]
LeadPriority = Literal["low", "normal", "high", "urgent"]
LeadSource = Literal["manual", "support", "ai_chat", "customer_intelligence"]


class AdminLeadStageHistoryRead(BaseModel):
    id: int
    from_status: str | None
    to_status: str
    changed_by_name: str | None
    reason: str | None
    created_at: datetime


class AdminLeadNoteRead(BaseModel):
    id: int
    body: str
    author_name: str | None
    created_at: datetime
    updated_at: datetime


class AdminLeadRead(BaseModel):
    id: int
    title: str
    source: str
    status: LeadStatus
    priority: LeadPriority
    score: int
    customer_user_id: int | None
    customer_name: str | None
    conversation_id: int | None
    product_id: int | None
    product_name: str | None
    category_id: int | None
    category_name: str | None
    owner_user_id: int | None
    owner_name: str | None
    converted_order_id: int | None
    converted_order_code: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    description: str | None
    next_action_at: datetime | None
    lost_reason: str | None
    converted_at: datetime | None
    lost_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminLeadDetail(AdminLeadRead):
    stage_history: list[AdminLeadStageHistoryRead]
    notes: list[AdminLeadNoteRead]


class AdminLeadCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=240)
    source: LeadSource = "manual"
    priority: LeadPriority = "normal"
    score: int = Field(default=0, ge=0, le=100)
    customer_user_id: int | None = Field(default=None, ge=1)
    conversation_id: int | None = Field(default=None, ge=1)
    product_id: int | None = Field(default=None, ge=1)
    category_id: int | None = Field(default=None, ge=1)
    owner_user_id: int | None = Field(default=None, ge=1)
    contact_name: str | None = Field(default=None, max_length=240)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=8000)
    next_action_at: datetime | None = None


class AdminLeadUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_updated_at: datetime
    title: str | None = Field(default=None, min_length=1, max_length=240)
    status: LeadStatus | None = None
    priority: LeadPriority | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    owner_user_id: int | None = Field(default=None, ge=1)
    product_id: int | None = Field(default=None, ge=1)
    category_id: int | None = Field(default=None, ge=1)
    converted_order_id: int | None = Field(default=None, ge=1)
    description: str | None = Field(default=None, max_length=8000)
    next_action_at: datetime | None = None
    lost_reason: str | None = Field(default=None, max_length=500)
    stage_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_transition_fields(self):
        changed_fields = self.model_fields_set - {"expected_updated_at", "stage_reason"}
        if not changed_fields:
            raise ValueError("At least one lead field must be changed")
        if self.status == "lost" and not (self.lost_reason or "").strip():
            raise ValueError("lost_reason is required when lead is lost")
        if self.status == "converted" and self.converted_order_id is None:
            raise ValueError("converted_order_id is required when lead is converted")
        return self


class AdminLeadNotePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=8000)
