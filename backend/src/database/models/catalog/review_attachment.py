from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import EXTERNAL_ID_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class ReviewAttachment(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "review_attachments"

    review_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(length=100), nullable=True)
    moderation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default=text("'pending'"), index=True)
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderated_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True, index=True)

    review: Mapped["Review"] = relationship(back_populates="attachments")
    moderated_by: Mapped["Admin | None"] = relationship(foreign_keys=[moderated_by_user_id])
