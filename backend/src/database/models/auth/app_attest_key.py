from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import EXTERNAL_ID_MAX_LENGTH, STATUS_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class AppAttestKey(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "app_attest_keys"
    __table_args__ = (
        Index("ix_app_attest_keys_user_active", "user_id", "is_active"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key_id: Mapped[str] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=False, unique=True, index=True)
    public_key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    receipt_b64: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str] = mapped_column(String(length=STATUS_MAX_LENGTH), nullable=False)
    counter: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))

    user: Mapped["User"] = relationship()
