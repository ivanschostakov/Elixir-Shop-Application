from pathlib import Path

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import API_BASE_URL
from src.product_media import build_products_media_url, resolve_product_image_path

from src.database import Base
from src.database.limits import (
    PRODUCT_DESCRIPTION_MAX_LENGTH,
    PRODUCT_EXPIRATION_MAX_LENGTH,
    PRODUCT_NAME_MAX_LENGTH,
    PRODUCT_SKU_MAX_LENGTH,
    PRODUCT_USAGE_MAX_LENGTH,
)
from src.database.mixins import SystemMixin
from src.database.models.catalog.variant import Variant


class Product(Base, SystemMixin):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(length=PRODUCT_SKU_MAX_LENGTH), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(length=PRODUCT_NAME_MAX_LENGTH), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(length=PRODUCT_DESCRIPTION_MAX_LENGTH), nullable=True)
    usage: Mapped[str | None] = mapped_column(String(length=PRODUCT_USAGE_MAX_LENGTH), nullable=True)
    expiration: Mapped[str | None] = mapped_column(String(length=PRODUCT_EXPIRATION_MAX_LENGTH), nullable=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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
