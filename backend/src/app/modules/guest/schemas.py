from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from src.app.modules.auth.schemas.responses import AuthUserRead
from src.app.modules.users.me.schemas.order import PaymentMethod
from src.app.modules.users.me.schemas.order_draft import DeliveryCalculationPayload, UpdateOrderDraftRecipientPayload
from src.database.limits import EMAIL_MAX_LENGTH
from src.database.schemas import BasketItemRead, DeliveryAddressRead, DeliveryRecipientRead, OrderRead
from src.integrations.delivery.schemas import CountryCode, DeliveryMode, DeliveryProvider


class GuestBasketItemPayload(BaseModel):
    variant_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=100)


class GuestBasketQuotePayload(BaseModel):
    items: list[GuestBasketItemPayload] = Field(default_factory=list, max_length=100)


class GuestBasketQuoteRead(BaseModel):
    id: int
    user_id: int
    items: list[BasketItemRead]
    delivery_address_id: int | None = None
    recipient_id: int | None = None
    delivery_address: DeliveryAddressRead | None = None
    recipient: DeliveryRecipientRead | None = None
    items_count: int = Field(ge=0)
    total_quantity: int = Field(ge=0)
    total_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    delivery_total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    grand_total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str
    delivery_period_min: int | None = None
    delivery_period_max: int | None = None
    has_unavailable_items: bool
    created_at: datetime
    updated_at: datetime


class GuestDeliveryAddressPayload(BaseModel):
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
    delivery_calculation: DeliveryCalculationPayload


class GuestOrderPayload(BaseModel):
    items: list[GuestBasketItemPayload] = Field(min_length=1, max_length=100)
    delivery_address: GuestDeliveryAddressPayload
    recipient: UpdateOrderDraftRecipientPayload
    payment_method: PaymentMethod


class GuestEmailCheckPayload(BaseModel):
    email: EmailStr = Field(max_length=EMAIL_MAX_LENGTH)


class GuestEmailCheckResponse(BaseModel):
    email: EmailStr
    exists: bool


class GuestOrderResponse(BaseModel):
    access_token: str
    refresh_token: str
    session_id: int
    token_type: str = "bearer"
    user: AuthUserRead
    order: OrderRead
    credentials_email_sent: bool
    credentials_email_error: str | None = None
