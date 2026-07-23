from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin


class IntegrationRun(Base, IdPkMixin):
    __tablename__ = "integration_runs"
    __table_args__ = (
        Index("ix_integration_runs_provider_started", "provider", "started_at"),
        Index("ix_integration_runs_target", "target_type", "target_id", "started_at"),
    )

    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running", server_default=text("'running'"), index=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("admins.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_type: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    target_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    retry_of_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("integration_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default=text("3"))
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    counters_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    requested_by: Mapped["Admin | None"] = relationship(foreign_keys=[requested_by_user_id])
    retry_of: Mapped["IntegrationRun | None"] = relationship(remote_side="IntegrationRun.id", foreign_keys=[retry_of_id])
