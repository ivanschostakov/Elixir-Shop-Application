from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class CommunityAttachment(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "community_attachments"

    message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("community_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    local_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_file_unique_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ready", server_default="ready")

    message: Mapped["CommunityMessage"] = relationship(back_populates="attachments")
