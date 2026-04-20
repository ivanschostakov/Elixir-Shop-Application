from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import BUSINESS_NAME_MAX_LENGTH, CURRENCY_CODE_MAX_LENGTH, PROMO_CODE_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class WebsiteReferralProfile(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "website_referral_profiles"

    website_identity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("website_identities.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    own_promo_code: Mapped[str | None] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=True, index=True)
    referrer_website_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    referrer_promo_code: Mapped[str | None] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=True)
    referral_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    referral_turnover_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    referral_turnover_currency: Mapped[str | None] = mapped_column(String(length=CURRENCY_CODE_MAX_LENGTH), nullable=True)
    monthly_paid_orders_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    monthly_paid_orders_currency: Mapped[str | None] = mapped_column(String(length=CURRENCY_CODE_MAX_LENGTH), nullable=True)
    tier_group_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tier_group_name: Mapped[str | None] = mapped_column(String(length=BUSINESS_NAME_MAX_LENGTH), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    website_identity: Mapped["WebsiteIdentity"] = relationship(back_populates="referral_profile")
