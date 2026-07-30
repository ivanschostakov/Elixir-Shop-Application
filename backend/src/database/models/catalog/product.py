from pathlib import Path

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import API_BASE_URL
from src.product_media import build_products_media_url, resolve_product_image_path

from src.database import Base
from src.database.limits import (
    PRODUCT_NAME_MAX_LENGTH,
    PRODUCT_SKU_MAX_LENGTH,
)
from src.database.mixins import SystemMixin
from src.database.models.catalog.variant import Variant


class Product(Base, SystemMixin):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "stock_reduction_override IS NULL OR stock_reduction_override >= 0",
            name="ck_products_stock_reduction_override_nonnegative",
        ),
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="ck_products_discount_percent_range",
        ),
    )

    sku: Mapped[str] = mapped_column(String(length=PRODUCT_SKU_MAX_LENGTH), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(length=PRODUCT_NAME_MAX_LENGTH), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage: Mapped[str | None] = mapped_column(Text, nullable=True)
    expiration: Mapped[str | None] = mapped_column(Text, nullable=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    stock_reduction_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_new_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )

    variants: Mapped[list["Variant"]] = relationship(
        "Variant",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by=(Variant.price.asc(), Variant.id.asc()),
        passive_deletes=True,
    )

    products_by_category: Mapped[list["ProductByCategory"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )
    certificates: Mapped[list["ProductCertificate"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="(ProductCertificate.sort_order, ProductCertificate.id)",
        passive_deletes=True,
    )
    favoured_products: Mapped[list["FavouredProduct"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    basket_items: Mapped[list["BasketItem"]] = relationship(back_populates="product", cascade="all, delete-orphan", passive_deletes=True)

    @property
    def image_path(self) -> Path | None:
        return resolve_product_image_path(product_id=self.id, system_id=self.system_id)

    @property
    def has_image(self) -> bool:
        return self.image_path is not None

    @property
    def image_url(self) -> str:
        return build_products_media_url(API_BASE_URL, self.image_path)
