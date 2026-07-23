from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AdminInvitation(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_invitations"
    __table_args__ = (
        Index(
            "uq_admin_invitations_pending_email",
            "email",
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
        Index("ix_admin_invitations_status", "accepted_at", "revoked_at", "expires_at"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    role_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    invited_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("admins.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    accepted_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("admins.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    send_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))

