from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class CommunityTelegramReaction(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "community_telegram_reactions"
    __table_args__ = (
        UniqueConstraint(
            "telegram_chat_id",
            "telegram_message_id",
            "actor_key",
            "emoji",
            name="uq_community_telegram_reactions_message_actor_emoji",
        ),
    )

    message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("community_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_key: Mapped[str] = mapped_column(String(96), nullable=False)
    emoji: Mapped[str] = mapped_column(String(32), nullable=False)

    message: Mapped["CommunityMessage"] = relationship(back_populates="telegram_reactions")


class CommunityTelegramReactionCount(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "community_telegram_reaction_counts"
    __table_args__ = (
        UniqueConstraint(
            "telegram_chat_id",
            "telegram_message_id",
            "emoji",
            name="uq_community_telegram_reaction_counts_message_emoji",
        ),
    )

    message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("community_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    emoji: Mapped[str] = mapped_column(String(32), nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    message: Mapped["CommunityMessage"] = relationship(back_populates="telegram_reaction_counts")
