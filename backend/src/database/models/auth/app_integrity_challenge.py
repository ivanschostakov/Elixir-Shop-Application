from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import EXTERNAL_ID_MAX_LENGTH, STATUS_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class AppIntegrityChallenge(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "app_integrity_challenges"
    __table_args__ = (
        Index(
            "ix_app_integrity_challenges_user_platform_purpose_action",
            "user_id",
            "platform",
            "purpose",
            "action",
        ),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge: Mapped[str] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=False, unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(length=STATUS_MAX_LENGTH), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(length=STATUS_MAX_LENGTH), nullable=False, index=True)
    action: Mapped[str | None] = mapped_column(String(length=STATUS_MAX_LENGTH), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()
