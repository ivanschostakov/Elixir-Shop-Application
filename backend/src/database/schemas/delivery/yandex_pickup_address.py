from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.integrations.delivery.schemas import CountryCode

from src.database.limits import (
    DELIVERY_ADDRESS_MAX_LENGTH,
    DELIVERY_COMMENT_MAX_LENGTH,
    DELIVERY_LABEL_MAX_LENGTH,
    DELIVERY_POINT_MAX_LENGTH,
    EMAIL_MAX_LENGTH,
    PERSON_NAME_MAX_LENGTH,
    PHONE_NUMBER_MAX_LENGTH,
)


class YandexPickupAddressBase(BaseModel):
    user_id: int = Field(gt=0)
    country_code: CountryCode
    name: str = Field(min_length=1, max_length=DELIVERY_LABEL_MAX_LENGTH)
    full_name: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    full_address: str = Field(min_length=1, max_length=DELIVERY_ADDRESS_MAX_LENGTH)
    shipment_point: str = Field(min_length=1, max_length=DELIVERY_POINT_MAX_LENGTH)
    comment: str | None = Field(default=None, max_length=DELIVERY_COMMENT_MAX_LENGTH)
    delivery_point: str = Field(min_length=1, max_length=DELIVERY_POINT_MAX_LENGTH)
    phone: str = Field(min_length=1, max_length=PHONE_NUMBER_MAX_LENGTH)
    email: EmailStr = Field(max_length=EMAIL_MAX_LENGTH)


class YandexPickupAddressCreate(YandexPickupAddressBase):
    pass


class YandexPickupAddressUpdate(BaseModel):
    country_code: CountryCode | None = None
    name: str | None = Field(default=None, min_length=1, max_length=DELIVERY_LABEL_MAX_LENGTH)
    full_name: str | None = Field(default=None, min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    full_address: str | None = Field(default=None, min_length=1, max_length=DELIVERY_ADDRESS_MAX_LENGTH)
    shipment_point: str | None = Field(default=None, min_length=1, max_length=DELIVERY_POINT_MAX_LENGTH)
    comment: str | None = Field(default=None, max_length=DELIVERY_COMMENT_MAX_LENGTH)
    delivery_point: str | None = Field(default=None, min_length=1, max_length=DELIVERY_POINT_MAX_LENGTH)
    phone: str | None = Field(default=None, min_length=1, max_length=PHONE_NUMBER_MAX_LENGTH)
    email: EmailStr | None = Field(default=None, max_length=EMAIL_MAX_LENGTH)


class YandexPickupAddressRead(YandexPickupAddressBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: Literal["YANDEX"]
    created_at: datetime
    updated_at: datetime
