from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AIChat(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "chats"
    __table_args__ = (UniqueConstraint("user_id", "scope", name="uq_chats_user_scope"), CheckConstraint("scope IN ('ordinary', 'mentor')", name="ck_chats_scope"))

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="ordinary", server_default="ordinary")
    conversation_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    user: Mapped["User"] = relationship(back_populates="ai_chats")
    messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AIMessage.id",
    )

    current_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
