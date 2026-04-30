from sqlalchemy import BigInteger, ForeignKey, CheckConstraint, String, Boolean, Integer, false, text as sqltext
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.limits import REVIEW_MAXIMUM_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class Review(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "reviews"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"), nullable=False, index=True)

    value: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(String(REVIEW_MAXIMUM_LENGTH), nullable=True)
    answer: Mapped[str] = mapped_column(String(REVIEW_MAXIMUM_LENGTH), nullable=True)

    likes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=sqltext("0"))
    dislikes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=sqltext("0"))

    moderated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

    __table_args__ = (
        CheckConstraint("value >= 0 AND value <= 5", name="check_review_value_0_5"),
        CheckConstraint("likes >= 0", name="check_likes_non_negative"),
        CheckConstraint("dislikes >= 0", name="check_dislikes_non_negative"),
    )
