from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class CommunityReport(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "community_reports"
    __table_args__ = (
        UniqueConstraint("reporter_id", "message_id", name="uq_community_reports_reporter_message"),
        CheckConstraint("status IN ('pending', 'dismissed', 'removed')", name="ck_community_reports_status"),
        CheckConstraint("reason IN ('spam', 'harassment', 'dangerous_content', 'inappropriate_content', 'other')", name="ck_community_reports_reason"),
    )

    reporter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("community_messages.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(32))
    details: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending", index=True)
    moderator_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"))
    moderation_note: Mapped[str] = mapped_column(Text, default="", server_default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reporter: Mapped["User"] = relationship()
    message: Mapped["CommunityMessage"] = relationship()
