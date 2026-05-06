from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import CURRENCY_CODE_MAX_LENGTH, EXTERNAL_ID_MAX_LENGTH, PROMO_CODE_MAX_LENGTH, STATUS_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class ReferralCommissionEntry(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "referral_commission_entries"

    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    buyer_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    referrer_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    referral_relationship_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("referral_relationships.id", ondelete="SET NULL"), nullable=True, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    promo_code: Mapped[str | None] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=True, index=True)
    buyer_discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    referrer_discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    commission_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    order_subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    currency: Mapped[str] = mapped_column(String(length=CURRENCY_CODE_MAX_LENGTH), nullable=False, default="RUB", server_default=text("'RUB'"))
    status: Mapped[str] = mapped_column(String(length=STATUS_MAX_LENGTH), nullable=False, default="posted", server_default=text("'posted'"), index=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=False, unique=True)

    order: Mapped["Order"] = relationship()
    buyer: Mapped["User | None"] = relationship(foreign_keys=[buyer_user_id])
    referrer: Mapped["User | None"] = relationship(back_populates="referral_commission_entries", foreign_keys=[referrer_user_id])
    referral_relationship: Mapped["ReferralRelationship | None"] = relationship()
    ledger_entries: Mapped[list["BusinessLedgerEntry"]] = relationship(back_populates="referral_commission_entry")
