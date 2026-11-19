from sqlalchemy import BigInteger, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class CommunityNotificationMute(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "community_notification_mutes"
    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_community_notification_mutes_user_topic"),
        Index("uq_community_notification_mutes_user_group", "user_id", "telegram_chat_id", unique=True, postgresql_where=text("topic_id IS NULL"), sqlite_where=text("topic_id IS NULL")),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # NULL silences the whole group; other rows preserve individual topic choices.
    topic_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("community_topics.id", ondelete="CASCADE"), nullable=True, index=True)
