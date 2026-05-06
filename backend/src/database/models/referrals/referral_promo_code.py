from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import PROMO_CODE_MAX_LENGTH, SOURCE_KIND_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class ReferralPromoCode(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "referral_promo_codes"

    code: Mapped[str] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=False, unique=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"), index=True)
    source_system: Mapped[str] = mapped_column(String(length=SOURCE_KIND_MAX_LENGTH), nullable=False, default="app", server_default=text("'app'"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    owner: Mapped["User"] = relationship(back_populates="owned_referral_promo_codes")
    benefit_applications: Mapped[list["OrderBenefitApplication"]] = relationship(back_populates="referral_promo_code")
