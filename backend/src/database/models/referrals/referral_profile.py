from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class ReferralProfile(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "referral_profiles"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    referral_discount_base_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))
    current_discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00"))

    user: Mapped["User"] = relationship(back_populates="referral_profile", foreign_keys=[user_id])
