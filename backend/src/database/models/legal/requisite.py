from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.limits import REQUISITE_TITLE_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class Requisite(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "requisites"

    title: Mapped[str] = mapped_column(String(length=REQUISITE_TITLE_MAX_LENGTH), nullable=False)
    config: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
