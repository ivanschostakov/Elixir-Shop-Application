from pydantic import BaseModel, EmailStr, Field, field_validator

from src.database.limits import EMAIL_MAX_LENGTH, USERNAME_MAX_LENGTH
from src.normalize import normalize_email


class UserLoginPayload(BaseModel):
    login: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("login", mode="before")
    @classmethod
    def _normalize_login(cls, value: object) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("Login is required")
        if "@" in normalized:
            email = normalize_email(normalized)
            if not email or len(email) > EMAIL_MAX_LENGTH:
                raise ValueError("Enter a valid email or username")
            return email
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
