from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AdminAlert(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_alerts"
    __table_args__ = (
        Index("ix_admin_alerts_active_severity", "resolved_at", "severity", "last_occurred_at"),
    )

    severity: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title_ru: Mapped[str] = mapped_column(String(240), nullable=False)
    title_en: Mapped[str] = mapped_column(String(240), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    last_occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True)

    resolved_by: Mapped["Admin | None"] = relationship(foreign_keys=[resolved_by_user_id])
    read_receipts: Mapped[list["AdminAlertReadReceipt"]] = relationship(
        back_populates="alert",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AdminAlertReadReceipt(Base, IdPkMixin):
    __tablename__ = "admin_alert_read_receipts"
    __table_args__ = (UniqueConstraint("alert_id", "admin_user_id", name="uq_admin_alert_read_receipt"),)

    alert_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("admin_alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    admin_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="CASCADE"), nullable=False, index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    alert: Mapped["AdminAlert"] = relationship(back_populates="read_receipts")
    admin: Mapped["Admin"] = relationship(foreign_keys=[admin_user_id])
