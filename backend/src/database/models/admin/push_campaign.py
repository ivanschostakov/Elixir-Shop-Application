from datetime import datetime

from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AdminPushCampaign(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_push_campaigns"
    __table_args__ = (Index("ix_admin_push_campaigns_status_scheduled", "status", "scheduled_at"),)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    goal: Mapped[str | None] = mapped_column(String(120), nullable=True)
    utm_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    template_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admin_push_campaign_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default=text("'draft'"), index=True)
    segment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admin_customer_segments.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True, index=True)
    audience_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    segment: Mapped["AdminCustomerSegment | None"] = relationship(foreign_keys=[segment_id])
    template: Mapped["AdminPushCampaignTemplate | None"] = relationship(foreign_keys=[template_id])
    created_by: Mapped["Admin | None"] = relationship(foreign_keys=[created_by_user_id])
    recipients: Mapped[list["AdminPushCampaignRecipient"]] = relationship(back_populates="campaign", cascade="all, delete-orphan", passive_deletes=True)


class AdminPushCampaignTemplate(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_push_campaign_templates"
    __table_args__ = (
        UniqueConstraint("code", name="uq_admin_push_campaign_templates_code"),
        Index("ix_admin_push_campaign_templates_active_category", "is_active", "category"),
    )

    code: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general", server_default=text("'general'"), index=True)
    name_ru: Mapped[str] = mapped_column(String(160), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    title_ru: Mapped[str] = mapped_column(String(180), nullable=False)
    title_en: Mapped[str] = mapped_column(String(180), nullable=False)
    body_ru: Mapped[str] = mapped_column(String(500), nullable=False)
    body_en: Mapped[str] = mapped_column(String(500), nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    goal: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class AdminPushCampaignRecipient(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_push_campaign_recipients"
    __table_args__ = (
        UniqueConstraint("campaign_id", "user_id", name="uq_admin_push_campaign_recipient"),
        Index("ix_admin_push_campaign_recipients_campaign_status", "campaign_id", "status", "id"),
    )

    campaign_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("admin_push_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default=text("'pending'"), index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    campaign: Mapped["AdminPushCampaign"] = relationship(back_populates="recipients")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
