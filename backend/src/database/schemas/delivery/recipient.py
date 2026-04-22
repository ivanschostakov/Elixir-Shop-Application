from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import EMAIL_MAX_LENGTH, PERSON_NAME_MAX_LENGTH, WEBSITE_PHONE_MAX_LENGTH


class DeliveryRecipientBase(BaseModel):
    user_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    surname: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    phone: str = Field(default="", max_length=WEBSITE_PHONE_MAX_LENGTH)
    email: str = Field(default="", max_length=EMAIL_MAX_LENGTH)


class DeliveryRecipientCreate(DeliveryRecipientBase):
    pass


class DeliveryRecipientRead(DeliveryRecipientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
