from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.database.limits import PROMO_CODE_MAX_LENGTH


class AuthUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr | None = None
    name: str
    surname: str
    phone_number: str
    is_active: bool
    is_verified: bool
    promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)


class AuthTokensBase(BaseModel):
    access_token: str
    refresh_token: str
    session_id: int
    token_type: Literal["bearer"] = "bearer"


class AuthTokensWithUserResponse(AuthTokensBase):
    user: AuthUserRead


class AuthVerificationRequiredResponse(BaseModel):
    email: EmailStr
    verification_required: bool = True
    message: str


class AuthRefreshResponse(AuthTokensBase):
    pass


class AuthLogoutResponse(BaseModel):
    ok: bool
    message: str
