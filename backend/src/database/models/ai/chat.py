from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AIChat(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "chats"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    conversation_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    user: Mapped["User"] = relationship(back_populates="ai_chat")
    messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AIMessage.id",
    )

    current_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
