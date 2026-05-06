from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import PROMO_CODE_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class ReferralProfile(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "referral_profiles"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    website_identity_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("website_identities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    initial_purchase_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    website_seed_purchase_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    app_paid_purchase_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    referral_discount_base_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    current_month_purchase_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    previous_month_purchase_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    current_discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    referrer_promo_code: Mapped[str | None] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=True, index=True)
    referrer_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    referrer_attached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    promo_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    own_promo_code: Mapped[str | None] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=True, unique=True)
    own_promo_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    website_seed_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    website_seeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="referral_profile", foreign_keys=[user_id])
    website_identity: Mapped["WebsiteIdentity | None"] = relationship(back_populates="app_referral_profile")
    referrer_user: Mapped["User | None"] = relationship(foreign_keys=[referrer_user_id])
