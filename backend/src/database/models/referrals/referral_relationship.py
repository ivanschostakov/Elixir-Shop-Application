from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import PROMO_CODE_MAX_LENGTH, SOURCE_KIND_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class ReferralRelationship(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "referral_relationships"

    referred_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    referrer_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    referral_promo_code_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("referral_promo_codes.id", ondelete="SET NULL"), nullable=True, index=True)
    referrer_promo_code: Mapped[str] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=False, index=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default=text("2"))
    source_system: Mapped[str] = mapped_column(String(length=SOURCE_KIND_MAX_LENGTH), nullable=False, default="app", server_default=text("'app'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_relationship_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("referral_relationships.id", ondelete="SET NULL"), nullable=True)

    referred_user: Mapped["User"] = relationship(back_populates="referral_relationships", foreign_keys=[referred_user_id])
    referrer_user: Mapped["User | None"] = relationship(back_populates="referrals_made", foreign_keys=[referrer_user_id])
    referral_promo_code: Mapped["ReferralPromoCode | None"] = relationship()
    benefit_applications: Mapped[list["OrderBenefitApplication"]] = relationship(back_populates="referral_relationship")
