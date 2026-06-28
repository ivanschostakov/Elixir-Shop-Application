from datetime import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import (
    EMAIL_MAX_LENGTH,
    PASSWORD_HASH_MAX_LENGTH,
    PERSON_NAME_MAX_LENGTH,
    PHONE_NUMBER_MAX_LENGTH,
)
from src.database.mixins import IdPkMixin, TimestampMixin


class User(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(length=EMAIL_MAX_LENGTH), nullable=True, unique=True)
    password_hash: Mapped[str] = mapped_column(String(length=PASSWORD_HASH_MAX_LENGTH), nullable=False)

    name: Mapped[str] = mapped_column(String(length=PERSON_NAME_MAX_LENGTH), nullable=False)
    surname: Mapped[str] = mapped_column(String(length=PERSON_NAME_MAX_LENGTH), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    phone_number: Mapped[str] = mapped_column(String(length=PHONE_NUMBER_MAX_LENGTH), nullable=False, unique=True)
    contact_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    moysklad_counterparty_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    email_verification_codes: Mapped[list["EmailVerificationCode"]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    admin: Mapped["Admin | None"] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True, uselist=False)
    website_identity: Mapped["WebsiteIdentity | None"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    delivery_addresses: Mapped[list["DeliveryAddress"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    delivery_recipients: Mapped[list["DeliveryRecipient"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    cdek_pickup_addresses: Mapped[list["CdekPickupAddress"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    yandex_pickup_addresses: Mapped[list["YandexPickupAddress"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    cdek_door_addresses: Mapped[list["CdekDoorAddress"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    favoured_products: Mapped[list["FavouredProduct"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    basket: Mapped["Basket | None"] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True, uselist=False)
    basket_items: Mapped[list["BasketItem"]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    order_drafts: Mapped[list["OrderDraft"]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    orders: Mapped[list["Order"]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    push_tokens: Mapped[list["UserPushToken"]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    app_promos_created: Mapped[list["AppPromo"]] = relationship(back_populates="created_by")
    order_benefit_applications: Mapped[list["OrderBenefitApplication"]] = relationship(back_populates="user")
    business_ledger_entries: Mapped[list["BusinessLedgerEntry"]] = relationship(back_populates="user")
    referral_profile: Mapped["ReferralProfile | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="ReferralProfile.user_id",
        uselist=False,
    )
    owned_referral_promo_codes: Mapped[list["ReferralPromoCode"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    referral_relationships: Mapped[list["ReferralRelationship"]] = relationship(
        back_populates="referred_user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="ReferralRelationship.referred_user_id",
    )
    referrals_made: Mapped[list["ReferralRelationship"]] = relationship(
        back_populates="referrer_user",
        foreign_keys="ReferralRelationship.referrer_user_id",
    )
    referral_commission_entries: Mapped[list["ReferralCommissionEntry"]] = relationship(
        back_populates="referrer",
        foreign_keys="ReferralCommissionEntry.referrer_user_id",
    )
    website_sync_events: Mapped[list["WebsiteSyncEvent"]] = relationship(back_populates="user")
    ai_chat: Mapped["AIChat | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    ai_messages: Mapped[list["AIMessage"]] = relationship(back_populates="user", passive_deletes=True)
