from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AdminSavedView(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_saved_views"

    owner_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("admins.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))

    owner: Mapped["Admin"] = relationship(foreign_keys=[owner_user_id])
