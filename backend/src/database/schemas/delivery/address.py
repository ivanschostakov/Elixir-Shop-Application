from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.integrations.delivery.schemas import CountryCode, DeliveryMode, DeliveryProvider


class DeliveryAddressBase(BaseModel):
    user_id: int = Field(ge=1)
    mode: DeliveryMode
    provider: DeliveryProvider
    country_code: CountryCode
    name: str = Field(min_length=1)
    full_address: str = Field(min_length=1)
    details: str | None = None
    city: str | None = None
    postal_code: str | None = None
    latitude: float
    longitude: float
    provider_reference: str | None = None


class DeliveryAddressCreate(DeliveryAddressBase):
    pass


class DeliveryAddressRead(DeliveryAddressBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
