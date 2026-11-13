from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.limits import EMAIL_MAX_LENGTH, PASSWORD_HASH_MAX_LENGTH


class UserPasswordReset(Base):
    __tablename__ = "user_password_resets"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH))
    code_hash: Mapped[str] = mapped_column(String(PASSWORD_HASH_MAX_LENGTH))
    password_fingerprint: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer)
