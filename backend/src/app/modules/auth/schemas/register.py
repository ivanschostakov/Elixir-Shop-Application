from pydantic import BaseModel, EmailStr, Field, field_validator

from src.database.limits import EMAIL_MAX_LENGTH, PERSON_NAME_MAX_LENGTH
from src.normalize import normalize_email


class UserRegisterPayload(BaseModel):
    email: EmailStr = Field(max_length=EMAIL_MAX_LENGTH)
    password: str = Field(min_length=8, max_length=100)
    name: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    surname: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: EmailStr | str) -> str:
        normalized = normalize_email(value)
        if not normalized:
            raise ValueError("Email is required")
        return normalized

    @field_validator("name", "surname", mode="before")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Field cannot be blank")
        return normalized


class UserRegisterVerifyPayload(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: EmailStr | str) -> str:
        normalized = normalize_email(value)
        if not normalized:
            raise ValueError("Email is required")
        return normalized


class UserVerificationCodeResendPayload(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: EmailStr | str) -> str:
        normalized = normalize_email(value)
        if not normalized:
            raise ValueError("Email is required")
        return normalized


class UserRegistrationStartedResponse(BaseModel):
    user_id: int
    email: EmailStr
    verification_required: bool = True
    message: str


class UserVerificationCodeSentResponse(BaseModel):
    email: EmailStr
    verification_required: bool = True
    message: str
