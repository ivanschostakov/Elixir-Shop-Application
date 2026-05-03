from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class WebhookDelivery(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "delivery_id",
            name="uq_webhook_deliveries_provider_delivery_id",
        ),
        UniqueConstraint(
            "provider",
            "signature_hash",
            "signature_timestamp",
            name="uq_webhook_deliveries_provider_signature_ts",
        ),
        CheckConstraint(
            "(delivery_id IS NOT NULL) OR "
            "(signature_hash IS NOT NULL AND signature_timestamp IS NOT NULL) OR "
            "(payload_hash IS NOT NULL)",
            name="ck_webhook_deliveries_has_dedupe_key",
        ),
        Index("ix_webhook_deliveries_provider_created_at", "provider", "created_at"),
    )

    provider: Mapped[str] = mapped_column(String(length=64), nullable=False, index=True)
    delivery_id: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    signature_hash: Mapped[str | None] = mapped_column(String(length=64), nullable=True)
    signature_timestamp: Mapped[str | None] = mapped_column(String(length=128), nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(length=64), nullable=True)
