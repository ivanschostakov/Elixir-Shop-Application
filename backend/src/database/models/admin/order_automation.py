from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AdminOrderAutomationRule(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_order_automation_rules"
    __table_args__ = (Index("ix_admin_order_automation_rules_enabled_priority", "is_enabled", "priority", "id"),)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"), index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default=text("100"))
    conditions_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    action_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_match_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped["Admin | None"] = relationship(foreign_keys=[created_by_user_id])
    executions: Mapped[list["AdminOrderAutomationExecution"]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AdminOrderAutomationExecution(Base, IdPkMixin):
    __tablename__ = "admin_order_automation_executions"
    __table_args__ = (
        UniqueConstraint("rule_id", "order_id", "fingerprint", name="uq_admin_order_automation_execution"),
        Index("ix_admin_order_automation_executions_rule_status", "rule_id", "status", "executed_at"),
    )

    rule_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("admin_order_automation_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    action_kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="running", server_default=text("'running'"), index=True)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    rule: Mapped["AdminOrderAutomationRule"] = relationship(back_populates="executions")
    order: Mapped["Order"] = relationship(foreign_keys=[order_id])
