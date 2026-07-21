from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AdminNote(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_notes"

    customer_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("admins.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    customer: Mapped["User"] = relationship(foreign_keys=[customer_user_id])
    author: Mapped["Admin | None"] = relationship(foreign_keys=[author_user_id])
