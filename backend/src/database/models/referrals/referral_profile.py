from decimal import Decimal

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class ReferralProfile(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "referral_profiles"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    reward_program: Mapped[str | None] = mapped_column(String(length=16), nullable=True, index=True)
    reward_program_selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reward_program_selection_source: Mapped[str | None] = mapped_column(String(length=32), nullable=True)
    reward_program_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    bitrix_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    bitrix_sync_status: Mapped[str] = mapped_column(
        String(length=32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        index=True,
    )
    bitrix_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bitrix_sync_error: Mapped[str | None] = mapped_column(String(length=500), nullable=True)
    partner_unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    referral_discount_base_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    current_discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))

    user: Mapped["User"] = relationship(back_populates="referral_profile", foreign_keys=[user_id])
