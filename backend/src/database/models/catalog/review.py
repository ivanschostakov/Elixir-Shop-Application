from datetime import datetime

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, CheckConstraint, String, Boolean, DateTime, Integer, false, text as sqltext
from sqlalchemy.dialects.postgresql import JSONB
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
    submitter_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    value: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str | None] = mapped_column(String(REVIEW_MAXIMUM_LENGTH), nullable=True)
    answer: Mapped[str | None] = mapped_column(String(REVIEW_MAXIMUM_LENGTH), nullable=True)
    internal_moderation_comment: Mapped[str | None] = mapped_column(String(4000), nullable=True)

    likes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=sqltext("0"))
    dislikes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=sqltext("0"))
    spam_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=sqltext("0"))
    profanity_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    duplicate_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    suspicious_ip_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    moderation_flags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=sqltext("'{}'::jsonb"))
    duplicate_group_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    moderated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderated_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("admins.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    appeal_status: Mapped[str] = mapped_column(String(32), nullable=False, default="none", server_default=sqltext("'none'"), index=True)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customer_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
    moderation_events: Mapped[list["ReviewModerationEvent"]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ReviewModerationEvent.created_at",
    )
