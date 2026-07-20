from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class CommunityTopic(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "community_topics"
    __table_args__ = (
        UniqueConstraint("telegram_chat_id", "telegram_thread_id", name="uq_community_topics_chat_thread"),
    )

    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    telegram_thread_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    icon_color: Mapped[int | None] = mapped_column(Integer, nullable=True)
    icon_custom_emoji_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    last_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    messages: Mapped[list["CommunityMessage"]] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    read_states: Mapped[list["CommunityTopicRead"]] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
