from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import (
    CURRENCY_CODE_MAX_LENGTH,
    EMAIL_MAX_LENGTH,
    ORDER_CODE_MAX_LENGTH,
    PROMO_CODE_MAX_LENGTH,
    STATUS_MAX_LENGTH,
)
from src.database.mixins import IdPkMixin, TimestampMixin


class AppReferralPurchase(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "app_referral_purchases"

    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    buyer_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_order_id: Mapped[str] = mapped_column(
        String(length=ORDER_CODE_MAX_LENGTH),
        nullable=False,
        unique=True,
        index=True,
    )
    bitrix_buyer_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    promo_code: Mapped[str | None] = mapped_column(
        String(length=PROMO_CODE_MAX_LENGTH),
        nullable=True,
        index=True,
    )
    bitrix_coupon_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    bitrix_discount_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    bitrix_purchase_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    coupon_use_count_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coupon_use_count_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(length=CURRENCY_CODE_MAX_LENGTH),
        nullable=False,
        default="RUB",
        server_default=text("'RUB'"),
    )
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    bitrix_sync_status: Mapped[str] = mapped_column(
        String(length=STATUS_MAX_LENGTH),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        index=True,
    )
    bitrix_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_error: Mapped[str | None] = mapped_column(String(length=500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(length=STATUS_MAX_LENGTH),
        nullable=False,
        default="posted",
        server_default=text("'posted'"),
        index=True,
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calculation_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    accruals: Mapped[list["AppReferralAccrual"]] = relationship(
        back_populates="purchase",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AppReferralAccrual.level",
    )


class AppReferralAccrual(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "app_referral_accruals"
    __table_args__ = (
        UniqueConstraint("purchase_id", "level", name="uq_app_referral_accrual_purchase_level"),
    )

    purchase_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_referral_purchases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    beneficiary_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    beneficiary_bitrix_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    beneficiary_email: Mapped[str | None] = mapped_column(String(length=EMAIL_MAX_LENGTH), nullable=True, index=True)
    beneficiary_name: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    bitrix_accrual_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    referral_bitrix_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    buyer_discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(7, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    referrer_discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(7, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    commission_percent: Mapped[Decimal] = mapped_column(
        Numeric(7, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    commission_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    currency: Mapped[str] = mapped_column(
        String(length=CURRENCY_CODE_MAX_LENGTH),
        nullable=False,
        default="RUB",
        server_default=text("'RUB'"),
    )
    status: Mapped[str] = mapped_column(
        String(length=STATUS_MAX_LENGTH),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    eligibility_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    purchase: Mapped["AppReferralPurchase"] = relationship(back_populates="accruals")
