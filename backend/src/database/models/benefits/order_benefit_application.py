from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import CURRENCY_CODE_MAX_LENGTH, PROMO_CODE_MAX_LENGTH, SOURCE_KIND_MAX_LENGTH, STATUS_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class OrderBenefitApplication(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "order_benefit_applications"

    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    website_identity_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("website_identities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_kind: Mapped[str] = mapped_column(String(length=SOURCE_KIND_MAX_LENGTH), nullable=False, index=True)
    website_coupon_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("website_coupons.id", ondelete="SET NULL"), nullable=True)
    website_discount_entitlement_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("website_discount_entitlements.id", ondelete="SET NULL"), nullable=True
    )
    website_bonus_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("website_bonus_accounts.id", ondelete="SET NULL"), nullable=True
    )
    app_promo_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_promos.id", ondelete="SET NULL"), nullable=True)
    referral_profile_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("referral_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    referral_promo_code_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("referral_promo_codes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    referral_relationship_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("referral_relationships.id", ondelete="SET NULL"), nullable=True, index=True
    )
    entered_code: Mapped[str | None] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=True)
    resolved_code: Mapped[str | None] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=True)
    resolved_referrer_website_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    bonus_spent_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(length=CURRENCY_CODE_MAX_LENGTH), nullable=True)
    status: Mapped[str] = mapped_column(
        String(length=STATUS_MAX_LENGTH), nullable=False, default="applied", server_default=text("'applied'"), index=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calculation_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    user: Mapped["User | None"] = relationship(back_populates="order_benefit_applications")
    website_identity: Mapped["WebsiteIdentity | None"] = relationship(back_populates="benefit_applications")
    website_coupon: Mapped["WebsiteCoupon | None"] = relationship(back_populates="benefit_applications")
    website_discount_entitlement: Mapped["WebsiteDiscountEntitlement | None"] = relationship(back_populates="benefit_applications")
    website_bonus_account: Mapped["WebsiteBonusAccount | None"] = relationship(back_populates="benefit_applications")
    app_promo: Mapped["AppPromo | None"] = relationship(back_populates="benefit_applications")
    referral_profile: Mapped["ReferralProfile | None"] = relationship()
    referral_promo_code: Mapped["ReferralPromoCode | None"] = relationship(back_populates="benefit_applications")
    referral_relationship: Mapped["ReferralRelationship | None"] = relationship(back_populates="benefit_applications")
    ledger_entries: Mapped[list["BusinessLedgerEntry"]] = relationship(back_populates="benefit_application")
