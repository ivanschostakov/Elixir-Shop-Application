from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.database.limits import EXTERNAL_ID_MAX_LENGTH, PAYMENT_METHOD_MAX_LENGTH, PAYMENT_STATUS_MAX_LENGTH

PaymentMethod = Literal["later", "sbp"]


class CreateOrderPayload(BaseModel):
    draft_id: int = Field(ge=1)
    payment_method: PaymentMethod


class CreatePaymentPayload(BaseModel):
    order_id: int = Field(ge=1)


class PaymentStatusRead(BaseModel):
    status: str = "success"
    order_id: int = Field(ge=1)
    order_number: int = Field(ge=1)
    payment_method: str | None = Field(default=None, max_length=PAYMENT_METHOD_MAX_LENGTH)
    payment_status: str | None = Field(default=None, max_length=PAYMENT_STATUS_MAX_LENGTH)
    payment_step: str | None = None
    invoice_id: str | None = Field(default=None, max_length=EXTERNAL_ID_MAX_LENGTH)
    qr_url: str | None = None
    qr_image: str | None = None
    expires_at: datetime | str | None = None
    is_paid: bool
    can_retry: bool
