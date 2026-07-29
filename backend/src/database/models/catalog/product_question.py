from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class ProductQuestion(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "product_questions"

    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    guest_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    text: Mapped[str] = mapped_column(String(2000), nullable=False)
    answer: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    internal_moderation_comment: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    moderated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderated_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("admins.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])
    moderated_by: Mapped["Admin | None"] = relationship(foreign_keys=[moderated_by_user_id])
