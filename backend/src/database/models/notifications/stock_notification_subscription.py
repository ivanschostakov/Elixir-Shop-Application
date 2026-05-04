from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class StockNotificationSubscription(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "stock_notification_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "variant_id", name="uq_stock_notification_subscriptions_user_variant"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("variants.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    last_seen_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()
    variant: Mapped["Variant"] = relationship()
