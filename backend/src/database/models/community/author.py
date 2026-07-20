from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class CommunityAuthor(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "community_authors"
    __table_args__ = (
        UniqueConstraint("kind", "telegram_peer_id", name="uq_community_authors_kind_peer"),
    )

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    telegram_peer_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    app_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_local_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["CommunityMessage"]] = relationship(back_populates="author")
