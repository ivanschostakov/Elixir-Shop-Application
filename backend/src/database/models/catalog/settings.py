from sqlalchemy import Boolean, CheckConstraint, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.mixins import TimestampMixin


class CatalogSettings(Base, TimestampMixin):
    __tablename__ = "catalog_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_catalog_settings_singleton"),
        CheckConstraint(
            "stock_reduction >= 0",
            name="ck_catalog_settings_stock_reduction_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    stock_reduction_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    stock_reduction: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
