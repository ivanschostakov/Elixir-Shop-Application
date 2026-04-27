from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import PRODUCT_NAME_MAX_LENGTH, PRODUCT_SKU_MAX_LENGTH, VARIANT_NAME_MAX_LENGTH, VARIANT_SKU_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class OrderItem(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "order_items"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    variant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(length=PRODUCT_NAME_MAX_LENGTH), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(length=PRODUCT_SKU_MAX_LENGTH), nullable=False)
    variant_name: Mapped[str] = mapped_column(String(length=VARIANT_NAME_MAX_LENGTH), nullable=False)
    variant_sku: Mapped[str | None] = mapped_column(String(length=VARIANT_SKU_MAX_LENGTH), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    order: Mapped["Order"] = relationship(back_populates="items")
