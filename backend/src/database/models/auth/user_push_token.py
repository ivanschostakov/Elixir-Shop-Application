from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import EXTERNAL_ID_MAX_LENGTH, ROUTE_PATH_MAX_LENGTH, STATUS_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class UserPushToken(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "user_push_tokens"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expo_push_token: Mapped[str] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=False, unique=True, index=True)
    platform: Mapped[str | None] = mapped_column(String(length=STATUS_MAX_LENGTH), nullable=True)
    current_path: Mapped[str | None] = mapped_column(String(length=ROUTE_PATH_MAX_LENGTH), nullable=True)

    user: Mapped["User"] = relationship(back_populates="push_tokens")
