from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.database.limits import EMAIL_MAX_LENGTH, PERSON_NAME_MAX_LENGTH, WEBSITE_PHONE_MAX_LENGTH
from src.normalize import normalize_person_name


class DeliveryRecipientBase(BaseModel):
    user_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    surname: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    phone: str = Field(default="", max_length=WEBSITE_PHONE_MAX_LENGTH)
    email: EmailStr | Literal[""] = Field(default="", max_length=EMAIL_MAX_LENGTH)

    @field_validator("name", "surname")
    @classmethod
    def _normalize_name_parts(cls, value: str) -> str:
        normalized = normalize_person_name(value, max_length=PERSON_NAME_MAX_LENGTH)
        if normalized is None:
            raise ValueError("Name fields must not be empty")
        return normalized


class DeliveryRecipientCreate(DeliveryRecipientBase):
    pass


class DeliveryRecipientRead(DeliveryRecipientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
