from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AdminPasswordReset(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_password_resets"
    __table_args__ = (
        Index("ix_admin_password_resets_user_active", "user_id", "used_at", "expires_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("admins.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
