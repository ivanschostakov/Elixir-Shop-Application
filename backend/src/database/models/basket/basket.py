from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class Basket(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "baskets"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)

    user: Mapped["User"] = relationship(back_populates="basket")
    items: Mapped[list["BasketItem"]] = relationship(back_populates="basket", cascade="all, delete-orphan", passive_deletes=True)
