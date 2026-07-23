from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class UserDevice(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "user_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "installation_id", name="uq_user_devices_user_installation"),
        Index("ix_user_devices_platform_version", "platform", "app_version"),
        Index("ix_user_devices_user_last_seen", "user_id", "last_seen_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    installation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    app_build: Mapped[str | None] = mapped_column(String(32), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    push_permission: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
        index=True,
    )
    install_source: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sessions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    user: Mapped["User"] = relationship(back_populates="devices")
    events: Mapped[list["UserEvent"]] = relationship(back_populates="device", passive_deletes=True)


class UserEvent(Base, IdPkMixin):
    __tablename__ = "user_events"
    __table_args__ = (
        Index("ix_user_events_user_occurred", "user_id", "occurred_at"),
        Index("ix_user_events_name_occurred", "event_name", "occurred_at"),
        Index("ix_user_events_entity", "entity_type", "entity_id"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("user_devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="app",
        server_default=text("'app'"),
        index=True,
    )
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    properties_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    attribution_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    user: Mapped["User"] = relationship(back_populates="events")
    device: Mapped["UserDevice | None"] = relationship(back_populates="events")


class CustomerMarketingProfile(Base, TimestampMixin):
    __tablename__ = "customer_marketing_profiles"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    lifecycle_stage: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="new",
        server_default=text("'new'"),
        index=True,
    )
    lead_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), index=True)
    engagement_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_event_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_platform: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    last_app_version: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    push_permission: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
        index=True,
    )
    preferred_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sessions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    total_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    product_views: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    category_views: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    searches_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    banner_clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    push_opens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    push_clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    cart_adds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    cart_removes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    checkout_started: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    checkout_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    orders_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    orders_paid: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    last_purchase_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="marketing_profile")


class CustomerConsent(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "customer_consents"
    __table_args__ = (
        UniqueConstraint("user_id", "purpose", "channel", name="uq_customer_consents_user_purpose_channel"),
        Index("ix_customer_consents_purpose_granted", "purpose", "is_granted"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(24), nullable=False, default="all", server_default=text("'all'"))
    is_granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="app", server_default=text("'app'"))
    policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="consents")


class CustomerAttribution(Base, TimestampMixin):
    __tablename__ = "customer_attribution"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    first_source: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    first_medium: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_campaign: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    first_content: Mapped[str | None] = mapped_column(String(160), nullable=True)
    first_term: Mapped[str | None] = mapped_column(String(160), nullable=True)
    first_referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    first_landing_page: Mapped[str | None] = mapped_column(String(500), nullable=True)
    first_touch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_source: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    last_medium: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_campaign: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    last_content: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_term: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_landing_page: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_touch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    install_source: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    user: Mapped["User"] = relationship(back_populates="attribution")
