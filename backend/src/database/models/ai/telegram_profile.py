"""Small durable memory for the existing Telegram AI conversation."""
from typing import Any
from datetime import datetime
from sqlalchemy import BigInteger, Integer, JSON, String, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base
from src.database.mixins import TimestampMixin

Json = JSON().with_variant(JSONB, "postgresql")


class TelegramAIProfile(Base, TimestampMixin):
    __tablename__ = "telegram_ai_profiles"
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    data: Mapped[dict[str, Any]] = mapped_column(Json, nullable=False, default=dict)
    receipts: Mapped[list[str]] = mapped_column(Json, nullable=False, default=list)


class TelegramAIJournal(Base, TimestampMixin):
    __tablename__ = "telegram_ai_journal"
    __table_args__ = (UniqueConstraint("telegram_user_id", "request_key", name="uq_tg_journal_request"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    data: Mapped[dict[str, Any]] = mapped_column(Json, nullable=False, default=dict)


class TelegramAIReminderSettings(Base, TimestampMixin):
    __tablename__ = "telegram_ai_reminder_settings"
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    timezone: Mapped[str] = mapped_column(String(80), default="Europe/Moscow", nullable=False)
    daily_time: Mapped[str | None] = mapped_column(String(5))
    next_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
