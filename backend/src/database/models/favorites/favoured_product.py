from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class FavouredProduct(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "favoured_products"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"), nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="favoured_products")
    product: Mapped["Product"] = relationship(back_populates="favoured_products")
