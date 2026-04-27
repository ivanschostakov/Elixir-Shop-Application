from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import (
    CURRENCY_CODE_MAX_LENGTH,
    EXTERNAL_ID_MAX_LENGTH,
    ORDER_DELIVERY_STRING_MAX_LENGTH,
    ORDER_DRAFT_COMMENT_MAX_LENGTH,
    PAYMENT_METHOD_MAX_LENGTH,
    PAYMENT_PROVIDER_MAX_LENGTH,
    PAYMENT_STATUS_MAX_LENGTH,
    STATUS_MAX_LENGTH,
)
from src.database.mixins import IdPkMixin, TimestampMixin


class Order(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "orders"

    draft_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("order_drafts.id"), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    delivery_address_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("delivery_addresses.id"), nullable=False, index=True)
    recipient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("delivery_recipients.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(length=STATUS_MAX_LENGTH), nullable=False, default="Создан", index=True)
    items_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    basket_subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    delivery_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(length=CURRENCY_CODE_MAX_LENGTH), nullable=False, default="RUB")
    delivery_period_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_period_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(String(length=ORDER_DRAFT_COMMENT_MAX_LENGTH), nullable=True)
    delivery_string: Mapped[str | None] = mapped_column(String(length=ORDER_DELIVERY_STRING_MAX_LENGTH), nullable=True)
    selected_delivery_service: Mapped[str] = mapped_column(String(length=STATUS_MAX_LENGTH), nullable=False, default="")
    selected_delivery_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    checkout_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    payment_method: Mapped[str | None] = mapped_column(String(length=PAYMENT_METHOD_MAX_LENGTH), nullable=True)
    payment_provider: Mapped[str | None] = mapped_column(String(length=PAYMENT_PROVIDER_MAX_LENGTH), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(length=PAYMENT_STATUS_MAX_LENGTH), nullable=False, default="draft", index=True)
    payment_invoice_id: Mapped[str | None] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=True, index=True)
    payment_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_error: Mapped[str | None] = mapped_column(String(length=ORDER_DRAFT_COMMENT_MAX_LENGTH), nullable=True)
    amocrm_lead_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    delivery_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_provider_ref: Mapped[str | None] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=True)
    yandex_request_id: Mapped[str | None] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_canceled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_shipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    draft: Mapped["OrderDraft | None"] = relationship(back_populates="orders")
    user: Mapped["User"] = relationship(back_populates="orders")
    delivery_address: Mapped["DeliveryAddress"] = relationship(back_populates="orders")
    recipient: Mapped["DeliveryRecipient"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OrderItem.id",
    )

    @property
    def order_number(self) -> int:
        return self.id
