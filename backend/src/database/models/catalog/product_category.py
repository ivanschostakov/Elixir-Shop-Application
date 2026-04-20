from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import PRODUCT_CATEGORY_DESCRIPTION_MAX_LENGTH, PRODUCT_CATEGORY_NAME_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class ProductCategory(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "product_categories"

    name: Mapped[str] = mapped_column(String(length=PRODUCT_CATEGORY_NAME_MAX_LENGTH), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(length=PRODUCT_CATEGORY_DESCRIPTION_MAX_LENGTH), nullable=True)
    products_by_category: Mapped[list["ProductByCategory"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", passive_deletes=True
    )
