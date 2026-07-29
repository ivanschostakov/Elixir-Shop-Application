from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import PRODUCT_CATEGORY_DESCRIPTION_MAX_LENGTH, PRODUCT_CATEGORY_NAME_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class ProductCategory(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "product_categories"
    __table_args__ = (
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="ck_product_categories_discount_percent_range",
        ),
    )

    name: Mapped[str] = mapped_column(String(length=PRODUCT_CATEGORY_NAME_MAX_LENGTH), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(length=PRODUCT_CATEGORY_DESCRIPTION_MAX_LENGTH), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    products_by_category: Mapped[list["ProductByCategory"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", passive_deletes=True
    )
