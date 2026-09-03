from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.schemas.ai.interactive import AIInteractivePayload
from src.database.mixins import IdPkMixin, TimestampMixin
from src.integrations.ai.enums import MessageSender, message_sender


class AIMessage(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "ai_messages"
    __table_args__ = (UniqueConstraint("user_id", "client_request_id", name="uq_ai_message_client_request"),)
    client_request_id: Mapped[str | None] = mapped_column(String(64))
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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
    def companion_cards(self) -> list[dict[str, Any]]:
        return (self.context_json or {}).get("companion_cards", [])

    @property
    def interactive(self) -> AIInteractivePayload | None:
        payload = (self.context_json or {}).get("interactive")
        if not isinstance(payload, dict):
            return None
        try:
            return AIInteractivePayload.model_validate(payload)
        except Exception:
            return None
