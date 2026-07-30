from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.limits import CURRENCY_CODE_MAX_LENGTH, ORDER_CODE_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class RewardProgramSelectionEvent(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "reward_program_selection_events"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_program: Mapped[str | None] = mapped_column(String(length=16), nullable=True)
    selected_program: Mapped[str] = mapped_column(String(length=16), nullable=False, index=True)
    source: Mapped[str] = mapped_column(
        String(length=32),
        nullable=False,
        default="user",
        server_default=text("'user'"),
    )
    reason: Mapped[str | None] = mapped_column(String(length=500), nullable=True)
    selected_by_admin_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )


class BonusProgramPurchase(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "bonus_program_purchases"

    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_order_id: Mapped[str] = mapped_column(
        String(length=ORDER_CODE_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(length=CURRENCY_CODE_MAX_LENGTH),
        nullable=False,
        default="RUB",
        server_default=text("'RUB'"),
    )
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(length=32),
        nullable=False,
        default="posted",
        server_default=text("'posted'"),
        index=True,
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calculation_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
