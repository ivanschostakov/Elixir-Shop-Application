from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class UserProductRecommendationSignal(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "user_product_recommendation_signals"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "product_id",
            name="uq_user_product_recommendation_signals_user_id_product_id",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    cart_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    purchase_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_carted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
