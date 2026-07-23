from sqlalchemy import BigInteger, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AdminDashboardPreference(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_dashboard_preferences"

    owner_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("admins.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    widgets_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))

    owner: Mapped["Admin"] = relationship(foreign_keys=[owner_user_id])
