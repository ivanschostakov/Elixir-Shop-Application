from datetime import datetime
import uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import SOURCE_KIND_MAX_LENGTH, STATUS_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class LoyaltyBonusCredit(Base, IdPkMixin, TimestampMixin):
    """An idempotent, expiring bonus credit mirrored to MoySklad."""

    __tablename__ = "loyalty_bonus_credits"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_loyalty_bonus_credits_idempotency_key"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    review_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("reviews.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_kind: Mapped[str] = mapped_column(
        String(length=SOURCE_KIND_MAX_LENGTH),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(length=160), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    spent_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    status: Mapped[str] = mapped_column(
        String(length=STATUS_MAX_LENGTH),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        index=True,
    )
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moysklad_bonus_program_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    moysklad_bonus_transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, unique=True)
    moysklad_debit_transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, unique=True)
    sync_error: Mapped[str | None] = mapped_column(String(length=500), nullable=True)

    user: Mapped["User"] = relationship()
    order: Mapped["Order | None"] = relationship()
    review: Mapped["Review | None"] = relationship()
