from sqlalchemy import BigInteger, Float, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import (
    COUNTRY_CODE_DB_ENUM,
    DELIVERY_MODE_DB_ENUM,
    DELIVERY_PROVIDER_DB_ENUM,
    IdPkMixin,
    TimestampMixin,
)


class DeliveryAddress(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "delivery_addresses"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(DELIVERY_MODE_DB_ENUM, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(DELIVERY_PROVIDER_DB_ENUM, nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(COUNTRY_CODE_DB_ENUM, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    full_address: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)

    user: Mapped["User"] = relationship(back_populates="delivery_addresses")
    baskets: Mapped[list["Basket"]] = relationship(back_populates="delivery_address")
    drafts: Mapped[list["OrderDraft"]] = relationship(back_populates="delivery_address")
    orders: Mapped[list["Order"]] = relationship(back_populates="delivery_address", passive_deletes="all")


Index(
    "uq_delivery_addresses_user_identity",
    DeliveryAddress.user_id,
    DeliveryAddress.mode,
    DeliveryAddress.provider,
    DeliveryAddress.country_code,
    DeliveryAddress.full_address,
    func.coalesce(DeliveryAddress.details, ""),
    func.coalesce(DeliveryAddress.city, ""),
    func.coalesce(DeliveryAddress.postal_code, ""),
    func.coalesce(DeliveryAddress.provider_reference, ""),
    unique=True,
)
