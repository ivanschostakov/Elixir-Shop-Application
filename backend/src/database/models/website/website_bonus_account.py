from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import CURRENCY_CODE_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class WebsiteBonusAccount(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "website_bonus_accounts"

    website_identity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("website_identities.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    website_bonus_account_external_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    currency: Mapped[str | None] = mapped_column(String(length=CURRENCY_CODE_MAX_LENGTH), nullable=True)
    website_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    website_identity: Mapped["WebsiteIdentity"] = relationship(back_populates="bonus_account_snapshot")
    benefit_applications: Mapped[list["OrderBenefitApplication"]] = relationship(back_populates="website_bonus_account")
