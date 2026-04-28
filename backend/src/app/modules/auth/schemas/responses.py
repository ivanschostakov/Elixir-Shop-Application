from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr

from src.database.schemas.website.website_identity import WebsiteIdentityRead


class AuthUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    name: str
    surname: str
    phone_number: str | None = None
    is_active: bool
    is_verified: bool


class AuthTokensBase(BaseModel):
    access_token: str
    refresh_token: str
    session_id: int
    token_type: Literal["bearer"] = "bearer"


class AuthTokensWithUserResponse(AuthTokensBase):
    user: AuthUserRead


class AuthTokensWithWebsiteIdentityResponse(AuthTokensBase):
    user: AuthUserRead
    website_identity: WebsiteIdentityRead


class AuthVerificationRequiredResponse(BaseModel):
    email: EmailStr
    verification_required: bool = True
    message: str


class AuthRefreshResponse(AuthTokensBase):
    pass


class AuthLogoutResponse(BaseModel):
    ok: bool
    message: str
