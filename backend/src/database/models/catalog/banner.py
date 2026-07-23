from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import BANNER_IMAGE_PATH_MAX_LENGTH, BANNER_LINK_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class Banner(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "banners"

    image_path: Mapped[str] = mapped_column(String(length=BANNER_IMAGE_PATH_MAX_LENGTH), nullable=False)
    desktop_image_path: Mapped[str | None] = mapped_column(String(length=BANNER_IMAGE_PATH_MAX_LENGTH), nullable=True)
    mobile_image_path: Mapped[str | None] = mapped_column(String(length=BANNER_IMAGE_PATH_MAX_LENGTH), nullable=True)
    title: Mapped[str | None] = mapped_column(String(240), nullable=True)
    inner_link: Mapped[str | None] = mapped_column(String(length=BANNER_LINK_MAX_LENGTH), nullable=True)
    outer_link: Mapped[str | None] = mapped_column(String(length=BANNER_LINK_MAX_LENGTH), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default=text("'draft'"), index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    audience_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    impression_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    clicks: Mapped[list["BannerClick"]] = relationship(back_populates="banner", cascade="all, delete-orphan", passive_deletes=True)
