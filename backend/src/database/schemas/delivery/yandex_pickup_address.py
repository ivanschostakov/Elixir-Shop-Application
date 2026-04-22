from uuid import UUID
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.integrations.delivery.schemas import CountryCode

from src.database.limits import (
    DELIVERY_ADDRESS_MAX_LENGTH,
    DELIVERY_LABEL_MAX_LENGTH,
)


class YandexPickupAddressBase(BaseModel):
    user_id: int = Field(gt=0)
    country_code: CountryCode
    name: str = Field(min_length=1, max_length=DELIVERY_LABEL_MAX_LENGTH)
    full_address: str = Field(min_length=1, max_length=DELIVERY_ADDRESS_MAX_LENGTH)
    platform_id: UUID


class YandexPickupAddressCreate(YandexPickupAddressBase):
    pass


class YandexPickupAddressUpdate(BaseModel):
    country_code: CountryCode | None = None
    name: str | None = Field(default=None, min_length=1, max_length=DELIVERY_LABEL_MAX_LENGTH)
    full_address: str | None = Field(default=None, min_length=1, max_length=DELIVERY_ADDRESS_MAX_LENGTH)
    platform_id: UUID | None = None


class YandexPickupAddressRead(YandexPickupAddressBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: Literal["YANDEX"]
    created_at: datetime
    updated_at: datetime
