from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import (
    BUSINESS_NAME_MAX_LENGTH,
    CURRENCY_CODE_MAX_LENGTH,
    LEDGER_NOTE_MAX_LENGTH,
    PROMO_CODE_MAX_LENGTH,
    SOURCE_KIND_MAX_LENGTH,
)
from src.database.mixins import IdPkMixin, TimestampMixin


class WebsiteCoupon(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "website_coupons"

    website_identity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("website_identities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    website_coupon_external_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True)
    coupon_code: Mapped[str] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=False, index=True)
    discount_rule_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    discount_rule_name: Mapped[str | None] = mapped_column(String(length=BUSINESS_NAME_MAX_LENGTH), nullable=True)
    discount_type: Mapped[str | None] = mapped_column(String(length=SOURCE_KIND_MAX_LENGTH), nullable=True)
    discount_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    discount_currency: Mapped[str | None] = mapped_column(String(length=CURRENCY_CODE_MAX_LENGTH), nullable=True)
    max_use: Mapped[int | None] = mapped_column(Integer, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(String(length=LEDGER_NOTE_MAX_LENGTH), nullable=True)
    website_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    website_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    website_identity: Mapped["WebsiteIdentity"] = relationship(back_populates="coupon_snapshots")
    benefit_applications: Mapped[list["OrderBenefitApplication"]] = relationship(back_populates="website_coupon")
