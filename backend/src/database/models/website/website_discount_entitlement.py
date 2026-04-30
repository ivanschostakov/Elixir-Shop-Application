from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import BUSINESS_NAME_MAX_LENGTH, CURRENCY_CODE_MAX_LENGTH, EXTERNAL_ID_MAX_LENGTH, SOURCE_KIND_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class WebsiteDiscountEntitlement(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "website_discount_entitlements"
    __table_args__ = (
        UniqueConstraint(
            "website_identity_id", "source_kind", "website_source_id", name="uq_website_discount_entitlements_identity_source"
        ),
    )

    website_identity_id: Mapped[int] = mapped_column(
        ForeignKey("website_identities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_kind: Mapped[str] = mapped_column(
        String(length=SOURCE_KIND_MAX_LENGTH), nullable=False, default="group", server_default=text("'group'")
    )
    website_source_id: Mapped[str | None] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=True)
    source_name: Mapped[str] = mapped_column(String(length=BUSINESS_NAME_MAX_LENGTH), nullable=False)
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(length=CURRENCY_CODE_MAX_LENGTH), nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    website_identity: Mapped["WebsiteIdentity"] = relationship(back_populates="discount_entitlements")
    benefit_applications: Mapped[list["OrderBenefitApplication"]] = relationship(back_populates="website_discount_entitlement")
