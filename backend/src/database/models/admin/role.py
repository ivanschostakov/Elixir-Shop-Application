from typing import Any

from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class AdminRole(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "admin_roles"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name_ru: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))

    assignments: Mapped[list["AdminRoleAssignment"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
