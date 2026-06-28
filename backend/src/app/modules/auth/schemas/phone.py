from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.database.limits import EMAIL_MAX_LENGTH, PERSON_NAME_MAX_LENGTH, PHONE_NUMBER_MAX_LENGTH
from src.normalize import normalize_phone


class _PhonePayload(BaseModel):
    phone_number: str = Field(min_length=1, max_length=PHONE_NUMBER_MAX_LENGTH)

    @field_validator("phone_number", mode="before")
    @classmethod
    def _normalize_phone_number(cls, value: str) -> str:
        normalized = normalize_phone(value)
        if not normalized:
            raise ValueError("Phone number is required")
        return normalized


class PhoneAuthStartPayload(_PhonePayload):
    pass


class PhoneAuthLoginPayload(_PhonePayload):
    password: str = Field(min_length=8, max_length=128)


class PhoneAuthClaimPayload(_PhonePayload):
    password: str = Field(min_length=8, max_length=128)
    email: EmailStr | None = Field(default=None, max_length=EMAIL_MAX_LENGTH)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: EmailStr | str | None) -> str | None:
        return str(value).strip().lower() if value is not None else None


class PhoneAuthRegisterPayload(_PhonePayload):
    name: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    surname: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    email: EmailStr | None = Field(default=None, max_length=EMAIL_MAX_LENGTH)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name", "surname", mode="before")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Field cannot be blank")
        return normalized

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: EmailStr | str | None) -> str | None:
        return str(value).strip().lower() if value is not None else None


class PhoneAuthVerifyPayload(_PhonePayload):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PhoneAuthCodeResendPayload(_PhonePayload):
    pass


class PhoneAuthStartResponse(BaseModel):
    phone_number: str
    next_step: Literal["login", "claim", "register"]
    email_required: bool = False
    email_hint: str | None = None
    message: str


class PhoneAuthVerificationRequiredResponse(BaseModel):
    phone_number: str
    email: EmailStr | None = None
    verification_required: bool = True
    message: str


class PhoneAuthCodeSentResponse(BaseModel):
    phone_number: str
    email: EmailStr | None = None
    verification_required: bool = True
    message: str
