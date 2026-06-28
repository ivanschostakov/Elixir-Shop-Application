from pydantic import BaseModel, EmailStr, Field, field_validator

from src.database.limits import EMAIL_MAX_LENGTH, PERSON_NAME_MAX_LENGTH, PHONE_NUMBER_MAX_LENGTH, USERNAME_MAX_LENGTH


class UserRegisterPayload(BaseModel):
    username: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)
    email: EmailStr = Field(max_length=EMAIL_MAX_LENGTH)
    password: str = Field(min_length=8, max_length=100)
    name: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    surname: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    phone_number: str = Field(min_length=1, max_length=PHONE_NUMBER_MAX_LENGTH)

    @field_validator("username", "name", "surname", "phone_number", mode="before")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Field cannot be blank")
        return normalized

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: EmailStr | str) -> str:
        return str(value).strip().lower()


class UserRegisterVerifyPayload(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class UserVerificationCodeResendPayload(BaseModel):
    email: EmailStr


class UserRegistrationStartedResponse(BaseModel):
    user_id: int
    email: EmailStr
    verification_required: bool = True
    message: str


class UserVerificationCodeSentResponse(BaseModel):
    email: EmailStr
    verification_required: bool = True
    message: str
