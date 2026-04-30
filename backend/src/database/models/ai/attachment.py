from pathlib import Path
from uuid import uuid4

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import ATTACHMENTS_DIR
from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin
from src.integrations.ai.enums import AttachmentType, attachment_type


def generate_filename() -> str:
    return uuid4().hex


class Attachment(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "attachments"

    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[AttachmentType] = mapped_column(attachment_type, nullable=False)

    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, default=generate_filename)

    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    message: Mapped["AIMessage"] = relationship(back_populates="attachments")

    @property
    def relative_path(self) -> Path:
        return Path(str(self.message_id)) / self.filename

    @property
    def path(self) -> Path:
        return ATTACHMENTS_DIR / self.relative_path
