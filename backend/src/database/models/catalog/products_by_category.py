from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class ProductByCategory(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "products_by_category"
    __table_args__ = (UniqueConstraint("product_id", "category_id", name="uq_products_by_category_product_id_category_id"),)

    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product: Mapped["Product"] = relationship(back_populates="products_by_category")
    category: Mapped["ProductCategory"] = relationship(back_populates="products_by_category")
