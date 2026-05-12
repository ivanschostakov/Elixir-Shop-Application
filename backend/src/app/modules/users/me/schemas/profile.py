from pydantic import BaseModel, EmailStr, Field, field_validator

from src.database.limits import EMAIL_MAX_LENGTH, PERSON_NAME_MAX_LENGTH, PHONE_NUMBER_MAX_LENGTH, USERNAME_MAX_LENGTH


class PersonalDataUpdatePayload(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=USERNAME_MAX_LENGTH)
    email: EmailStr | None = Field(default=None, max_length=EMAIL_MAX_LENGTH)
    name: str | None = Field(default=None, min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    surname: str | None = Field(default=None, min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    phone_number: str | None = Field(default=None, max_length=PHONE_NUMBER_MAX_LENGTH)
    password: str | None = Field(default=None, min_length=8, max_length=100)

    @field_validator("username", "name", "surname", "phone_number")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).strip().lower() if value is not None else None
