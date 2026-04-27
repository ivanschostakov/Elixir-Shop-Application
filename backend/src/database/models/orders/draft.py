from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import (
    CURRENCY_CODE_MAX_LENGTH,
    ORDER_DRAFT_COMMENT_MAX_LENGTH,
    ORDER_DRAFT_NAME_MAX_LENGTH,
    STATUS_MAX_LENGTH,
)
from src.database.mixins import IdPkMixin, TimestampMixin


class OrderDraft(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "order_drafts"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    delivery_address_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("delivery_addresses.id"),
        nullable=True,
        index=True,
    )
    recipient_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("delivery_recipients.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(length=STATUS_MAX_LENGTH), nullable=False, default="draft", index=True)
    items_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    basket_subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    delivery_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(length=CURRENCY_CODE_MAX_LENGTH), nullable=False, default="RUB")
    delivery_period_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_period_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    draft_name: Mapped[str | None] = mapped_column(String(length=ORDER_DRAFT_NAME_MAX_LENGTH), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(length=ORDER_DRAFT_COMMENT_MAX_LENGTH), nullable=True)

    user: Mapped["User"] = relationship(back_populates="order_drafts")
    delivery_address: Mapped["DeliveryAddress | None"] = relationship(back_populates="drafts")
    recipient: Mapped["DeliveryRecipient | None"] = relationship(back_populates="drafts")
    orders: Mapped[list["Order"]] = relationship(back_populates="draft", passive_deletes="all")
    items: Mapped[list["OrderDraftItem"]] = relationship(
        back_populates="draft",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OrderDraftItem.id",
    )
