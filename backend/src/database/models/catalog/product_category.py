from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Numeric, String, text
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
        CheckConstraint(
            "app_display_order >= 0",
            name="ck_product_categories_app_display_order_nonnegative",
        ),
    )

    name: Mapped[str] = mapped_column(String(length=PRODUCT_CATEGORY_NAME_MAX_LENGTH), nullable=False, unique=True)
    website_category_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(String(length=PRODUCT_CATEGORY_DESCRIPTION_MAX_LENGTH), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    is_visible_in_app: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        index=True,
    )
    app_display_order: Mapped[int] = mapped_column(
        nullable=False,
        default=10_000,
        server_default=text("10000"),
        index=True,
    )
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    products_by_category: Mapped[list["ProductByCategory"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", passive_deletes=True
    )
