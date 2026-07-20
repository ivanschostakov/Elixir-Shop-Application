from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class CommunityTopicRead(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "community_topic_reads"
    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_community_topic_reads_user_topic"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("community_topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    last_read_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    topic: Mapped["CommunityTopic"] = relationship(back_populates="read_states")
