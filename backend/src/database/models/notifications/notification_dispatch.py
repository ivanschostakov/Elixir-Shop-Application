from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import ufa_now
from src.database import Base
from src.database.mixins import IdPkMixin


class NotificationDispatch(Base, IdPkMixin):
    __tablename__ = "notification_dispatches"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(length=64), nullable=False, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(length=255), nullable=False, index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=ufa_now, server_default=func.now(), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict)

    user: Mapped["User"] = relationship()
