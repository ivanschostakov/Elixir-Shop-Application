from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import CURRENCY_CODE_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class Basket(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "baskets"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    delivery_address_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("delivery_addresses.id"), nullable=True, index=True)
    recipient_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("delivery_recipients.id"), nullable=True, index=True)
    delivery_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00")
    )
    currency: Mapped[str] = mapped_column(
        String(length=CURRENCY_CODE_MAX_LENGTH), nullable=False, default="RUB", server_default=text("'RUB'")
    )
    delivery_period_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_period_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="basket")
    delivery_address: Mapped["DeliveryAddress | None"] = relationship(back_populates="baskets")
    recipient: Mapped["DeliveryRecipient | None"] = relationship(back_populates="baskets")
    items: Mapped[list["BasketItem"]] = relationship(back_populates="basket", cascade="all, delete-orphan", passive_deletes=True)
