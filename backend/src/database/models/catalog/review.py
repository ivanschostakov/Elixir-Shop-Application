from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, CheckConstraint, String, Boolean, DateTime, Integer, false, text as sqltext
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import REVIEW_MAXIMUM_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class Review(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "reviews"

    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"), nullable=False, index=True)

    guest_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    guest_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    value: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str | None] = mapped_column(String(REVIEW_MAXIMUM_LENGTH), nullable=True)
    answer: Mapped[str | None] = mapped_column(String(REVIEW_MAXIMUM_LENGTH), nullable=True)

    likes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=sqltext("0"))
    dislikes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=sqltext("0"))

    moderated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderated_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("admins.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("value >= 0 AND value <= 5", name="check_review_value_0_5"),
        CheckConstraint("likes >= 0", name="check_likes_non_negative"),
        CheckConstraint("dislikes >= 0", name="check_dislikes_non_negative"),
    )

    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])
    moderated_by: Mapped["Admin | None"] = relationship(foreign_keys=[moderated_by_user_id])
    attachments: Mapped[list["ReviewAttachment"]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
