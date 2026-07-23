from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminRoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name_ru: str
    name_en: str
    permissions: list[str]
    description_ru: str = ""
    description_en: str = ""


class AdminUserRead(BaseModel):
    id: int
    email: EmailStr | None
    name: str
    surname: str
    locale: Literal["ru", "en"]


class AdminPrincipal(BaseModel):
    user: AdminUserRead
    roles: list[str]
    permissions: list[str]


class AdminLoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AdminChallengeResponse(BaseModel):
    status: Literal["mfa_required", "mfa_setup_required"]
    challenge_token: str
    expires_in: int


class AdminMfaSetupPayload(BaseModel):
    challenge_token: str = Field(min_length=20)


class AdminMfaSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class AdminMfaVerifyPayload(AdminMfaSetupPayload):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class AdminAuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    principal: AdminPrincipal


class AdminSessionRead(BaseModel):
    id: int
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    revoked_at: datetime | None
    current: bool = False


class AdminLocalePayload(BaseModel):
    locale: Literal["ru", "en"]


class AdminOkResponse(BaseModel):
    ok: bool = True
