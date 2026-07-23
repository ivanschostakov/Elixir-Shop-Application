from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AdminCustomerSegment(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_customer_segments"
    __table_args__ = (UniqueConstraint("owner_user_id", "name", name="uq_admin_customer_segments_owner_name"),)

    owner_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    filters_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    segment_type: Mapped[str] = mapped_column(String(24), nullable=False, default="dynamic", server_default=text("'dynamic'"), index=True)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    owner: Mapped["Admin"] = relationship(foreign_keys=[owner_user_id])
    snapshot_items: Mapped[list["AdminCustomerSegmentSnapshotItem"]] = relationship(back_populates="segment", cascade="all, delete-orphan", passive_deletes=True)
    history_events: Mapped[list["AdminCustomerSegmentHistory"]] = relationship(back_populates="segment", cascade="all, delete-orphan", passive_deletes=True)


class AdminCustomerSegmentSnapshotItem(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_customer_segment_snapshot_items"
    __table_args__ = (UniqueConstraint("segment_id", "user_id", name="uq_admin_customer_segment_snapshot_user"),)

    segment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("admin_customer_segments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"), index=True)

    segment: Mapped["AdminCustomerSegment"] = relationship(back_populates="snapshot_items")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])


class AdminCustomerSegmentHistory(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_customer_segment_history"

    segment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("admin_customer_segments.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    segment: Mapped["AdminCustomerSegment"] = relationship(back_populates="history_events")
    actor: Mapped["Admin | None"] = relationship(foreign_keys=[actor_user_id])
