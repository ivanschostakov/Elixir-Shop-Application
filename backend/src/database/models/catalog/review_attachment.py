from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import EXTERNAL_ID_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class ReviewAttachment(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "review_attachments"

    review_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(length=100), nullable=True)

    review: Mapped["Review"] = relationship(back_populates="attachments")
