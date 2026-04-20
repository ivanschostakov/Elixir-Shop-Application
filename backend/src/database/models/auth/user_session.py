from datetime import datetime, timedelta

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import REFRESH_TOKEN_LIFETIME_DAYS, ufa_now
from src.database import Base
from src.database.limits import IP_ADDRESS_MAX_LENGTH, REFRESH_TOKEN_HASH_MAX_LENGTH, USER_AGENT_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


def session_expires_at() -> datetime:
    return ufa_now() + timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS)


class UserSession(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "user_sessions"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(length=REFRESH_TOKEN_HASH_MAX_LENGTH), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=session_expires_at)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    user_agent: Mapped[str | None] = mapped_column(String(length=USER_AGENT_MAX_LENGTH), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(length=IP_ADDRESS_MAX_LENGTH), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")
