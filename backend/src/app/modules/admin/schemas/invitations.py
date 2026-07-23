from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class AdminInvitationCreatePayload(BaseModel):
    email: EmailStr
    role_codes: list[str] = Field(min_length=1, max_length=7)
    confirm_superadmin: bool = False

    @field_validator("role_codes")
    @classmethod
    def normalize_role_codes(cls, value: list[str]) -> list[str]:
        normalized = sorted({code.strip().lower() for code in value if code.strip()})
        if not normalized:
            raise ValueError("At least one role is required")
        return normalized


class AdminInvitationTokenPayload(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class AdminInvitationAcceptPayload(AdminInvitationTokenPayload):
    name: str | None = Field(default=None, max_length=120)
    surname: str | None = Field(default=None, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class AdminInvitationRead(BaseModel):
    id: int
    email: EmailStr
    role_codes: list[str]
    role_names_ru: list[str]
    role_names_en: list[str]
    invited_by_name: str
    status: Literal["pending", "accepted", "expired", "revoked"]
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    last_sent_at: datetime
    send_count: int


class AdminInvitationPreview(BaseModel):
    email: EmailStr
    role_codes: list[str]
    role_names_ru: list[str]
    role_names_en: list[str]
    invited_by_name: str
    status: Literal["pending", "accepted", "expired", "revoked"]
    expires_at: datetime
    existing_user: bool


class AdminInvitationAcceptResponse(BaseModel):
    email: EmailStr
    requires_mfa_setup: bool = True
    login_path: str = "/login"
