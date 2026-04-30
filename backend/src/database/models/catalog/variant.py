from decimal import Decimal
from pathlib import Path

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import API_BASE_URL
from src.product_media import build_products_media_url, resolve_variant_image_path

from src.database import Base
from src.database.limits import VARIANT_NAME_MAX_LENGTH, VARIANT_SKU_MAX_LENGTH
from src.database.mixins import SystemMixin


class Variant(Base, SystemMixin):
    __tablename__ = "doses"

    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)

    sku: Mapped[str | None] = mapped_column(String(length=VARIANT_SKU_MAX_LENGTH), nullable=True)
    name: Mapped[str] = mapped_column(String(length=VARIANT_NAME_MAX_LENGTH), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="variants")
    basket_items: Mapped[list["BasketItem"]] = relationship(back_populates="variant", cascade="all, delete-orphan", passive_deletes=True)

    @property
    def image_path(self) -> Path | None:
        return resolve_variant_image_path(product_id=self.product_id, system_id=self.system_id)

    @property
    def has_image(self) -> bool:
        return self.image_path is not None

    @property
    def image_url(self) -> str:
        return build_products_media_url(API_BASE_URL, self.image_path)
