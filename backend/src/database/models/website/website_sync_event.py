from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import EXTERNAL_ID_MAX_LENGTH, LEDGER_NOTE_MAX_LENGTH, SOURCE_KIND_MAX_LENGTH, STATUS_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class WebsiteSyncEvent(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "website_sync_events"

    order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    website_identity_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("website_identities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(length=SOURCE_KIND_MAX_LENGTH), nullable=False, index=True)
    external_order_id: Mapped[str | None] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=True, index=True)
    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(length=STATUS_MAX_LENGTH), nullable=False, default="pending", server_default=text("'pending'"), index=True
    )
    error_message: Mapped[str | None] = mapped_column(String(length=LEDGER_NOTE_MAX_LENGTH), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User | None"] = relationship(back_populates="website_sync_events")
    website_identity: Mapped["WebsiteIdentity | None"] = relationship(back_populates="sync_events")
