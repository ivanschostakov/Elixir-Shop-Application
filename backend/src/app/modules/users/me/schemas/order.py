from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from src.database.limits import EXTERNAL_ID_MAX_LENGTH, ORDER_CODE_MAX_LENGTH, PAYMENT_METHOD_MAX_LENGTH, PAYMENT_STATUS_MAX_LENGTH, PROMO_CODE_MAX_LENGTH

PaymentMethod = Literal["later", "sbp"]


class CreateOrderPayload(BaseModel):
    draft_id: int | None = Field(default=None, ge=1)
    payment_method: PaymentMethod
    code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)
    requested_deposit_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class CreatePaymentPayload(BaseModel):
    order_id: int = Field(ge=1)


class PaymentStatusRead(BaseModel):
    status: str = "success"
    order_id: int = Field(ge=1)
    order_code: str = Field(min_length=1, max_length=ORDER_CODE_MAX_LENGTH)
    order_number: str = Field(min_length=1, max_length=ORDER_CODE_MAX_LENGTH)
    payment_method: str | None = Field(default=None, max_length=PAYMENT_METHOD_MAX_LENGTH)
    payment_status: str | None = Field(default=None, max_length=PAYMENT_STATUS_MAX_LENGTH)
    payment_step: str | None = None
    invoice_id: str | None = Field(default=None, max_length=EXTERNAL_ID_MAX_LENGTH)
    qr_url: str | None = None
    qr_image: str | None = None
    expires_at: datetime | str | None = None
    is_paid: bool
    can_retry: bool
