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
    PROMO_CODE_MAX_LENGTH,
    TELEGRAM_USERNAME_MAX_LENGTH,
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
    phone_number: Mapped[str | None] = mapped_column(String(length=PHONE_NUMBER_MAX_LENGTH), nullable=True, unique=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(length=TELEGRAM_USERNAME_MAX_LENGTH), nullable=True)
    telegram_phone_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contact_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    moysklad_counterparty_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    promo_code: Mapped[str | None] = mapped_column(String(length=PROMO_CODE_MAX_LENGTH), nullable=True, index=True)

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    email_verification_codes: Mapped[list["EmailVerificationCode"]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    admin: Mapped["Admin | None"] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True, uselist=False)
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
    order_benefit_applications: Mapped[list["OrderBenefitApplication"]] = relationship(back_populates="user")
    referral_profile: Mapped["ReferralProfile | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="ReferralProfile.user_id",
        uselist=False,
    )
    ai_chat: Mapped["AIChat | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    ai_messages: Mapped[list["AIMessage"]] = relationship(back_populates="user", passive_deletes=True)
