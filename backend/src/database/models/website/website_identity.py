from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import WEBSITE_CITY_MAX_LENGTH, WEBSITE_EMAIL_MAX_LENGTH, WEBSITE_LOGIN_MAX_LENGTH, WEBSITE_PHONE_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class WebsiteIdentity(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "website_identities"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    website_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    website_login: Mapped[str] = mapped_column(String(length=WEBSITE_LOGIN_MAX_LENGTH), nullable=False)
    website_email: Mapped[str | None] = mapped_column(String(length=WEBSITE_EMAIL_MAX_LENGTH), nullable=True)
    website_name: Mapped[str | None] = mapped_column(String(length=WEBSITE_LOGIN_MAX_LENGTH), nullable=True)
    website_last_name: Mapped[str | None] = mapped_column(String(length=WEBSITE_LOGIN_MAX_LENGTH), nullable=True)
    website_second_name: Mapped[str | None] = mapped_column(String(length=WEBSITE_LOGIN_MAX_LENGTH), nullable=True)
    website_phone: Mapped[str | None] = mapped_column(String(length=WEBSITE_PHONE_MAX_LENGTH), nullable=True)
    website_mobile: Mapped[str | None] = mapped_column(String(length=WEBSITE_PHONE_MAX_LENGTH), nullable=True)
    website_city: Mapped[str | None] = mapped_column(String(length=WEBSITE_CITY_MAX_LENGTH), nullable=True)
    website_registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    website_last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    group_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    group_names: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    custom_fields: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    referral_program: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    bonus_account: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    discount_groups: Mapped[list[dict]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    active_coupons: Mapped[list[dict]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    recent_used_coupons: Mapped[list[dict]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="website_identity")
    referral_profile: Mapped["WebsiteReferralProfile | None"] = relationship(
        back_populates="website_identity", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )
    bonus_account_snapshot: Mapped["WebsiteBonusAccount | None"] = relationship(
        back_populates="website_identity", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )
    discount_entitlements: Mapped[list["WebsiteDiscountEntitlement"]] = relationship(
        back_populates="website_identity", cascade="all, delete-orphan", passive_deletes=True
    )
    coupon_snapshots: Mapped[list["WebsiteCoupon"]] = relationship(
        back_populates="website_identity", cascade="all, delete-orphan", passive_deletes=True
    )
    benefit_applications: Mapped[list["OrderBenefitApplication"]] = relationship(back_populates="website_identity")
    ledger_entries: Mapped[list["BusinessLedgerEntry"]] = relationship(back_populates="website_identity")
    sync_events: Mapped[list["WebsiteSyncEvent"]] = relationship(back_populates="website_identity")
