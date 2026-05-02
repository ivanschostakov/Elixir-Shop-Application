from decimal import Decimal
import re

from pydantic import BaseModel, Field, field_validator

from src.database.limits import (
    CURRENCY_CODE_MAX_LENGTH,
    EMAIL_MAX_LENGTH,
    ORDER_DRAFT_COMMENT_MAX_LENGTH,
    ORDER_DRAFT_NAME_MAX_LENGTH,
    PERSON_NAME_MAX_LENGTH,
    WEBSITE_PHONE_MAX_LENGTH,
)
from src.integrations.delivery.schemas import CountryCode, DeliveryMode, DeliveryProvider
from src.normalize import normalize_person_name

RECIPIENT_PHONE_RE = re.compile(r"^\+?\d{10,15}$")
RECIPIENT_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class DeliveryCalculationPayload(BaseModel):
    delivery_sum: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    period_min: int = Field(ge=0)
    period_max: int = Field(ge=0)
    currency: str = Field(min_length=1, max_length=CURRENCY_CODE_MAX_LENGTH)


class CreateOrderDraftPayload(BaseModel):
    mode: DeliveryMode | None = None
    provider: DeliveryProvider | None = None
    country_code: CountryCode | None = None
    name: str | None = Field(default=None, min_length=1)
    full_address: str | None = Field(default=None, min_length=1)
    details: str | None = None
    city: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    provider_reference: str | None = None
    draft_name: str | None = Field(default=None, max_length=ORDER_DRAFT_NAME_MAX_LENGTH)
    delivery_calculation: DeliveryCalculationPayload | None = None


class UpdateOrderDraftDeliveryAddressPayload(BaseModel):
    mode: DeliveryMode | None = None
    provider: DeliveryProvider | None = None
    country_code: CountryCode | None = None
    name: str | None = None
    full_address: str = Field(min_length=1)
    details: str | None = None
    city: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    provider_reference: str | None = None
    delivery_calculation: DeliveryCalculationPayload | None = None


class UpdateOrderDraftRecipientPayload(BaseModel):
    name: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    surname: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    phone: str = Field(min_length=1, max_length=WEBSITE_PHONE_MAX_LENGTH)
    email: str = Field(min_length=1, max_length=EMAIL_MAX_LENGTH)

    @field_validator("name", "surname")
    @classmethod
    def _validate_name_parts(cls, value: str) -> str:
        normalized = normalize_person_name(value, max_length=PERSON_NAME_MAX_LENGTH)
        if not normalized:
            raise ValueError("Name fields must not be empty")
        return normalized

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str) -> str:
        normalized = re.sub(r"[\s()-]", "", value.strip())
        if not RECIPIENT_PHONE_RE.fullmatch(normalized):
            raise ValueError("Phone must be in format +79991234567")
        return normalized

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not RECIPIENT_EMAIL_RE.fullmatch(normalized):
            raise ValueError("Email format is invalid")
        return normalized


class UpdateOrderDraftPayload(BaseModel):
    draft_name: str | None = Field(default=None, max_length=ORDER_DRAFT_NAME_MAX_LENGTH)
    comment: str | None = Field(default=None, max_length=ORDER_DRAFT_COMMENT_MAX_LENGTH)
    delivery_address_id: int | None = Field(default=None, ge=1)
    recipient_id: int | None = Field(default=None, ge=1)
    new_recipient: UpdateOrderDraftRecipientPayload | None = None
    new_delivery_address: UpdateOrderDraftDeliveryAddressPayload | None = None
    sync_basket_items: bool = False
