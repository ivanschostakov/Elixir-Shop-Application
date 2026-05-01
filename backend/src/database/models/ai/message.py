from typing import Any

from sqlalchemy import JSON, BigInteger, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.schemas.ai.interactive import AIInteractivePayload
from src.database.mixins import IdPkMixin, TimestampMixin
from src.integrations.ai.enums import MessageSender, message_sender


class AIMessage(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "ai_messages"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    sender: Mapped[MessageSender] = mapped_column(message_sender, nullable=False)
    context_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    user: Mapped["User"] = relationship(back_populates="ai_messages")
    chat: Mapped["AIChat"] = relationship(back_populates="messages")
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Attachment.id",
    )
    usage: Mapped["AIMessageUsage | None"] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

    @property
    def interactive(self) -> AIInteractivePayload | None:
        payload = (self.context_json or {}).get("interactive")
        if not isinstance(payload, dict):
            return None
        try:
            return AIInteractivePayload.model_validate(payload)
        except Exception:
            return None
