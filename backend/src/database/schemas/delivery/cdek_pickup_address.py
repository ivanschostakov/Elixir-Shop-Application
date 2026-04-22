from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.integrations.delivery.schemas import CountryCode

from src.database.limits import (
    DELIVERY_ADDRESS_MAX_LENGTH,
    DELIVERY_LABEL_MAX_LENGTH,
    DELIVERY_POINT_MAX_LENGTH,
)


class CdekPickupAddressBase(BaseModel):
    user_id: int = Field(gt=0)
    country_code: CountryCode
    name: str = Field(min_length=1, max_length=DELIVERY_LABEL_MAX_LENGTH)
    full_address: str = Field(min_length=1, max_length=DELIVERY_ADDRESS_MAX_LENGTH)
    delivery_point: str = Field(min_length=1, max_length=DELIVERY_POINT_MAX_LENGTH)


class CdekPickupAddressCreate(CdekPickupAddressBase):
    pass


class CdekPickupAddressUpdate(BaseModel):
    country_code: CountryCode | None = None
    name: str | None = Field(default=None, min_length=1, max_length=DELIVERY_LABEL_MAX_LENGTH)
    full_address: str | None = Field(default=None, min_length=1, max_length=DELIVERY_ADDRESS_MAX_LENGTH)
    delivery_point: str | None = Field(default=None, min_length=1, max_length=DELIVERY_POINT_MAX_LENGTH)


class CdekPickupAddressRead(CdekPickupAddressBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: Literal["CDEK"]
    created_at: datetime
    updated_at: datetime
