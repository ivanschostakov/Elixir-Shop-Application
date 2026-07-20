from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class CommunityTelegramPart(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "community_telegram_parts"
    __table_args__ = (
        UniqueConstraint("telegram_chat_id", "telegram_message_id", name="uq_community_telegram_parts_chat_message"),
    )

    message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("community_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    message: Mapped["CommunityMessage"] = relationship(back_populates="telegram_parts")
