from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import TimestampMixin
from src.integrations.ai.enums import BotModel, bot_model


class AIMessageUsage(Base, TimestampMixin):
    __tablename__ = "ai_message_usage"

    message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ai_messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bot_model: Mapped[BotModel] = mapped_column(bot_model, nullable=False)
    openai_model: Mapped[str] = mapped_column(String(length=120), nullable=False)

    message: Mapped["AIMessage"] = relationship(back_populates="usage")
