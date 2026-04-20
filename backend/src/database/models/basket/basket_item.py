from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class BasketItem(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "basket_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_basket_items_quantity_positive"),
        UniqueConstraint("basket_id", "dose_id", name="uq_basket_items_basket_id_dose_id"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    basket_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("baskets.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id: Mapped[int] = mapped_column("dose_id", BigInteger, ForeignKey("doses.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    user: Mapped["User"] = relationship(back_populates="basket_items")
    basket: Mapped["Basket"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="basket_items")
    variant: Mapped["Variant"] = relationship(back_populates="basket_items")
