"""Durable companion state. Provider conversations are never the source of truth."""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin

Json = JSON().with_variant(JSONB, "postgresql")


class AICompanionProfile(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "ai_companion_profiles"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(Json, default=dict, nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(Json, default=dict, nullable=False)
    target_history: Mapped[list] = mapped_column(Json, default=list, nullable=False)


class AICompanionPlan(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "ai_companion_plans"
    __table_args__ = (UniqueConstraint("user_id", "course_key", "version", name="uq_companion_plan_version"), Index("uq_companion_current_plan", "user_id", unique=True, postgresql_where=text("is_current AND status IN ('active', 'paused')"), sqlite_where=text("is_current AND status IN ('active', 'paused')")),)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_key: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(Json, nullable=False)


class AICompanionEvent(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "ai_companion_events"
    __table_args__ = (UniqueConstraint("plan_id", "event_key", name="uq_companion_event"),)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_companion_plans.id", ondelete="CASCADE"), index=True)
    event_key: Mapped[str] = mapped_column(String(160), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict[str, Any]] = mapped_column(Json, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class AICompanionEntry(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "ai_companion_entries"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(Json, nullable=False)
    source: Mapped[str] = mapped_column(String(24), default="manual", nullable=False)
    source_message_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ai_messages.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class AICompanionReminder(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "ai_companion_reminders"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_companion_reminder"),)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ai_companion_events.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ai_messages.id", ondelete="SET NULL"))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIProviderResource(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "ai_provider_resources"
    __table_args__ = (UniqueConstraint("kind", "external_id", name="uq_ai_provider_resource"),)
    # Nullable on account removal so an external deletion retry can finish.
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AICompanionOperation(Base, IdPkMixin, TimestampMixin):
    """Receipt for retries of confirmed actions; not a second diary."""
    __tablename__ = "ai_companion_operations"
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_companion_operation"),)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(Json, nullable=False)
