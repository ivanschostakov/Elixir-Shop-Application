from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import BUSINESS_NAME_MAX_LENGTH, CURRENCY_CODE_MAX_LENGTH, PROMO_CODE_MAX_LENGTH, SOURCE_KIND_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class AppPromo(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "app_promos"

    code: Mapped[str] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(length=BUSINESS_NAME_MAX_LENGTH), nullable=False)
    source_kind: Mapped[str] = mapped_column(
        String(length=SOURCE_KIND_MAX_LENGTH), nullable=False, default="app", server_default=text("'app'")
    )
    benefit_kind: Mapped[str] = mapped_column(String(length=SOURCE_KIND_MAX_LENGTH), nullable=False)
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(length=CURRENCY_CODE_MAX_LENGTH), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    max_total_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_uses_per_user: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stacking_policy: Mapped[str] = mapped_column(
        String(length=SOURCE_KIND_MAX_LENGTH), nullable=False, default="exclusive", server_default=text("'exclusive'")
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_by: Mapped["User | None"] = relationship(back_populates="app_promos_created")
    benefit_applications: Mapped[list["OrderBenefitApplication"]] = relationship(back_populates="app_promo")
