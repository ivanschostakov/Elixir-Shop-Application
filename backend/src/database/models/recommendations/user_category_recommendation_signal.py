from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class UserCategoryRecommendationSignal(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "user_category_recommendation_signals"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "category_id",
            name="uq_user_category_recommendation_signals_user_id_category_id",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
