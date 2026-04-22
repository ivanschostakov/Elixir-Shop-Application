from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import (
    DELIVERY_ADDRESS_MAX_LENGTH,
    DELIVERY_CITY_MAX_LENGTH,
    DELIVERY_COMMENT_MAX_LENGTH,
    DELIVERY_LABEL_MAX_LENGTH,
    DELIVERY_POSTAL_CODE_MAX_LENGTH,
    EXTERNAL_ID_MAX_LENGTH,
)
from src.integrations.delivery.schemas import CountryCode, DeliveryMode, DeliveryProvider


class DeliveryAddressBase(BaseModel):
    user_id: int = Field(ge=1)
    mode: DeliveryMode
    provider: DeliveryProvider
    country_code: CountryCode
    name: str = Field(min_length=1, max_length=DELIVERY_LABEL_MAX_LENGTH)
    full_address: str = Field(min_length=1, max_length=DELIVERY_ADDRESS_MAX_LENGTH)
    details: str | None = Field(default=None, max_length=DELIVERY_COMMENT_MAX_LENGTH)
    city: str | None = Field(default=None, max_length=DELIVERY_CITY_MAX_LENGTH)
    postal_code: str | None = Field(default=None, max_length=DELIVERY_POSTAL_CODE_MAX_LENGTH)
    latitude: float
    longitude: float
    provider_reference: str | None = Field(default=None, max_length=EXTERNAL_ID_MAX_LENGTH)


class DeliveryAddressCreate(DeliveryAddressBase):
    pass


class DeliveryAddressRead(DeliveryAddressBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
