from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin
from src.integrations.ai.enums import BotModel, MessageSender, bot_model, message_sender


class AIMessage(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "ai_messages"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    sender: Mapped[MessageSender] = mapped_column(message_sender, nullable=False)
    bot_model: Mapped[BotModel] = mapped_column(bot_model, nullable=False)

    tokens: Mapped[int] = mapped_column(nullable=False)

    user: Mapped["User"] = relationship(back_populates="ai_messages")
    chat: Mapped["AIChat"] = relationship(back_populates="messages")
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Attachment.id",
    )
