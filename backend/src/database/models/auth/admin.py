from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class AdminRoleAssignment(Base):
    __tablename__ = "admin_role_assignments"

    admin_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("admins.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("admin_roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("admins.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    admin: Mapped["Admin"] = relationship(
        back_populates="role_assignments",
        foreign_keys=[admin_user_id],
    )
    role: Mapped["AdminRole"] = relationship(back_populates="assignments")


class Admin(Base):
    __tablename__ = "admins"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locale: Mapped[str] = mapped_column(String(5), nullable=False, default="ru", server_default=text("'ru'"))

    user: Mapped["User"] = relationship(back_populates="admin")
    role_assignments: Mapped[list["AdminRoleAssignment"]] = relationship(
        back_populates="admin",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="AdminRoleAssignment.admin_user_id",
    )
