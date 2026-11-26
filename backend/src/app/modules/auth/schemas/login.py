from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator

from src.database.limits import EMAIL_MAX_LENGTH, USERNAME_MAX_LENGTH
from src.normalize import EMAIL_ADAPTER, normalize_email


# Verify existing credentials as supplied; new-password policy belongs to signup/reset.
SignInPassword = Annotated[str, Field(min_length=1, max_length=255)]


class UserLoginPayload(BaseModel):
    login: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)
    password: SignInPassword

    @field_validator("login", mode="before")
    @classmethod
    def _normalize_login(cls, value: object) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("Login is required")
        if "@" in normalized:
            try:
                email = str(EMAIL_ADAPTER.validate_python(normalized)).lower()
            except ValidationError as exc:
                raise ValueError("Enter a valid email address") from exc
            if len(email) > EMAIL_MAX_LENGTH:
                raise ValueError("Email is too long")
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
