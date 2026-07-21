from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class CommunityMessage(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "community_messages"
    __table_args__ = (
        UniqueConstraint("app_user_id", "client_id", name="uq_community_messages_user_client"),
    )

    topic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("community_topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("community_authors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    app_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reply_to_message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("community_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    telegram_media_group_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    unsupported_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(24), nullable=False, default="sent", server_default="sent")
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_attempts: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    next_delivery_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    topic: Mapped["CommunityTopic"] = relationship(back_populates="messages")
    author: Mapped["CommunityAuthor | None"] = relationship(back_populates="messages")
    reply_to: Mapped["CommunityMessage | None"] = relationship(remote_side="CommunityMessage.id")
    attachments: Mapped[list["CommunityAttachment"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CommunityAttachment.id",
    )
    telegram_parts: Mapped[list["CommunityTelegramPart"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CommunityTelegramPart.telegram_message_id",
    )
    reactions: Mapped[list["CommunityReaction"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CommunityReaction.id",
    )
    telegram_reactions: Mapped[list["CommunityTelegramReaction"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CommunityTelegramReaction.id",
    )
    telegram_reaction_counts: Mapped[list["CommunityTelegramReactionCount"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CommunityTelegramReactionCount.id",
    )
