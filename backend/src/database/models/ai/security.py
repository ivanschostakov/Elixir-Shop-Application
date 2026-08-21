from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, JSON, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AIChatAccessBan(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "ai_chat_access_bans"
    __table_args__ = (
        Index("ix_ai_chat_access_bans_lookup", "ban_type", "subject", "is_active"),
        Index("ix_ai_chat_access_bans_active", "is_active", "created_at"),
    )

    ban_type: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(254), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admin_identities.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admin_identities.id", ondelete="SET NULL"), nullable=True)

    created_by: Mapped["AdminIdentity | None"] = relationship(foreign_keys=[created_by_user_id])
    revoked_by: Mapped["AdminIdentity | None"] = relationship(foreign_keys=[revoked_by_user_id])


class AIChatSecurityEvent(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "ai_chat_security_events"
    __table_args__ = (
        Index("ix_ai_chat_security_events_user_created", "user_id", "created_at"),
        Index("ix_ai_chat_security_events_ip_created", "ip_address", "created_at"),
        Index("ix_ai_chat_security_events_risk_created", "is_suspicious", "created_at"),
    )

    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="accepted", server_default="accepted")
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_suspicious: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    risk_reasons: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list, server_default=text("'[]'::jsonb"))
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    user: Mapped["User"] = relationship()
