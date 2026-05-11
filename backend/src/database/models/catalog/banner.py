from sqlalchemy import Boolean, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.limits import BANNER_IMAGE_PATH_MAX_LENGTH, BANNER_LINK_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class Banner(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "banners"

    image_path: Mapped[str] = mapped_column(String(length=BANNER_IMAGE_PATH_MAX_LENGTH), nullable=False)
    inner_link: Mapped[str | None] = mapped_column(String(length=BANNER_LINK_MAX_LENGTH), nullable=True)
    outer_link: Mapped[str | None] = mapped_column(String(length=BANNER_LINK_MAX_LENGTH), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
