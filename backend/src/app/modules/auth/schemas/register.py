from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from src.database.limits import EMAIL_MAX_LENGTH, PERSON_NAME_MAX_LENGTH, PROMO_CODE_MAX_LENGTH
from src.normalize import normalize_email


class UserRegisterPayload(BaseModel):
    email: EmailStr = Field(max_length=EMAIL_MAX_LENGTH)
    password: str = Field(min_length=8, max_length=100)
    name: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    surname: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    reward_program: Literal["bonus", "partner"] | None = None
    promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    select_program_after_registration: bool = False

    @model_validator(mode="after")
    def _validate_program(self):
        self.promo_code = self.promo_code.strip() if self.promo_code else None
        if self.promo_code and self.reward_program != "partner":
            raise ValueError("A promo code requires the partner program")
        return self

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
