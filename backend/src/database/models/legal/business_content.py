from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class BusinessContentPage(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "business_content_pages"

    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    title_ru: Mapped[str] = mapped_column(String(240), nullable=False)
    title_en: Mapped[str] = mapped_column(String(240), nullable=False)
    body_ru: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    body_en: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    link_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default=text("'draft'"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    updated_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True, index=True)

    versions: Mapped[list["BusinessContentVersion"]] = relationship(back_populates="page", cascade="all, delete-orphan", passive_deletes=True, order_by="BusinessContentVersion.version")
    updated_by: Mapped["Admin | None"] = relationship(foreign_keys=[updated_by_user_id])


class BusinessContentVersion(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "business_content_versions"

    page_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("business_content_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True, index=True)
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    page: Mapped["BusinessContentPage"] = relationship(back_populates="versions")
    actor: Mapped["Admin | None"] = relationship(foreign_keys=[actor_user_id])
