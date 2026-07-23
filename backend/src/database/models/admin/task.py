from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AdminTask(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_tasks"
    __table_args__ = (
        Index("ix_admin_tasks_assignee_status_due", "assignee_user_id", "status", "due_at"),
        Index("ix_admin_tasks_customer_status", "customer_user_id", "status"),
        Index("ix_admin_tasks_sla_status_resolution", "status", "resolution_due_at"),
    )

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open", server_default=text("'open'"), index=True)
    priority: Mapped[str] = mapped_column(String(24), nullable=False, default="normal", server_default=text("'normal'"), index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_policy_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admin_sla_policies.id", ondelete="SET NULL"), nullable=True, index=True)
    response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    first_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    customer_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=True, index=True)
    assignee_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True, index=True)

    customer: Mapped["User | None"] = relationship(foreign_keys=[customer_user_id])
    order: Mapped["Order | None"] = relationship(foreign_keys=[order_id])
    assignee: Mapped["Admin"] = relationship(foreign_keys=[assignee_user_id])
    created_by: Mapped["Admin | None"] = relationship(foreign_keys=[created_by_user_id])
    sla_policy: Mapped["AdminSlaPolicy | None"] = relationship(foreign_keys=[sla_policy_id])
