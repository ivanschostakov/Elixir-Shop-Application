from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class ProductCertificate(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "product_certificates"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "website_file_id",
            name="uq_product_certificates_product_id_website_file_id",
        ),
    )

    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    website_file_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(length=500), nullable=False)
    original_name: Mapped[str | None] = mapped_column(String(length=500), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    url: Mapped[str] = mapped_column(String(length=2048), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product: Mapped["Product"] = relationship(back_populates="certificates")
