from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import (
    EMAIL_MAX_LENGTH,
    PASSWORD_HASH_MAX_LENGTH,
    PERSON_NAME_MAX_LENGTH,
)
from src.database.mixins import IdPkMixin, TimestampMixin


class AdminIdentity(Base, IdPkMixin, TimestampMixin):
    """Independent credentials for the admin panel.

    Admin identities deliberately live outside ``users`` so a customer profile
    can be deleted, disabled, or use a different password without affecting
    staff access.
    """

    __tablename__ = "admin_identities"
    __table_args__ = (
        UniqueConstraint("email", name="uq_admin_identities_email"),
    )

    email: Mapped[str] = mapped_column(
        String(length=EMAIL_MAX_LENGTH),
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(length=PASSWORD_HASH_MAX_LENGTH),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(length=PERSON_NAME_MAX_LENGTH),
        nullable=False,
    )
    surname: Mapped[str] = mapped_column(
        String(length=PERSON_NAME_MAX_LENGTH),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    admin: Mapped["Admin | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    sessions: Mapped[list["AdminSession"]] = relationship(
        back_populates="identity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
