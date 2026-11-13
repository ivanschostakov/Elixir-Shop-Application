from pydantic import BaseModel, EmailStr, Field, field_validator

from src.database.limits import EMAIL_MAX_LENGTH
from src.normalize import normalize_email


class UserPasswordResetRequest(BaseModel):
    email: EmailStr = Field(max_length=EMAIL_MAX_LENGTH)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        normalized = normalize_email(value)
        if not normalized:
            raise ValueError("Email is required")
        return normalized


class UserPasswordResetVerify(UserPasswordResetRequest):
    code: str = Field(pattern=r"^[0-9]{6}$")


class UserPasswordResetNewPassword(UserPasswordResetRequest):
    password: str = Field(min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def reject_blank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be blank")
        return value


class UserPasswordResetConfirm(UserPasswordResetNewPassword, UserPasswordResetVerify):
    pass


class UserPasswordResetComplete(UserPasswordResetNewPassword):
    reset_token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class UserPasswordResetVerified(BaseModel):
    reset_token: str


class UserPasswordResetResponse(BaseModel):
    ok: bool = True
