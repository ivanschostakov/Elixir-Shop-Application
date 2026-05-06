from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import (
    CURRENCY_CODE_MAX_LENGTH,
    EXTERNAL_ID_MAX_LENGTH,
    LEDGER_NOTE_MAX_LENGTH,
    PROMO_CODE_MAX_LENGTH,
    SOURCE_KIND_MAX_LENGTH,
    STATUS_MAX_LENGTH,
)
from src.database.mixins import IdPkMixin, TimestampMixin


class BusinessLedgerEntry(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "business_ledger_entries"

    order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    order_benefit_application_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("order_benefit_applications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    referral_commission_entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("referral_commission_entries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    website_identity_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("website_identities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    entry_type: Mapped[str] = mapped_column(String(length=SOURCE_KIND_MAX_LENGTH), nullable=False)
    direction: Mapped[str] = mapped_column(String(length=SOURCE_KIND_MAX_LENGTH), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(length=CURRENCY_CODE_MAX_LENGTH), nullable=False)
    source_system: Mapped[str] = mapped_column(String(length=SOURCE_KIND_MAX_LENGTH), nullable=False)
    source_code: Mapped[str | None] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=True)
    status: Mapped[str] = mapped_column(
        String(length=STATUS_MAX_LENGTH), nullable=False, default="posted", server_default=text("'posted'")
    )
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(String(length=LEDGER_NOTE_MAX_LENGTH), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=True, unique=True)

    benefit_application: Mapped["OrderBenefitApplication | None"] = relationship(back_populates="ledger_entries")
    referral_commission_entry: Mapped["ReferralCommissionEntry | None"] = relationship(back_populates="ledger_entries")
    user: Mapped["User | None"] = relationship(back_populates="business_ledger_entries")
    website_identity: Mapped["WebsiteIdentity | None"] = relationship(back_populates="ledger_entries")
