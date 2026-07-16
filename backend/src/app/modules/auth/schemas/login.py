from pydantic import BaseModel, EmailStr, Field, field_validator

from src.normalize import normalize_email


class UserLoginPayload(BaseModel):
    login: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("login", mode="before")
    @classmethod
    def _normalize_login(cls, value: EmailStr | str) -> str:
        normalized = normalize_email(value)
        if not normalized:
            raise ValueError("Email is required")
        return normalized


class UserLoginVerifyPayload(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: EmailStr | str) -> str:
        normalized = normalize_email(value)
        if not normalized:
            raise ValueError("Email is required")
        return normalized
