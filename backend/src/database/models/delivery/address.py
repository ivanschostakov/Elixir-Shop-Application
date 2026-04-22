from sqlalchemy import BigInteger, Float, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import (
    DELIVERY_ADDRESS_MAX_LENGTH,
    DELIVERY_CITY_MAX_LENGTH,
    DELIVERY_COMMENT_MAX_LENGTH,
    DELIVERY_LABEL_MAX_LENGTH,
    DELIVERY_POSTAL_CODE_MAX_LENGTH,
    EXTERNAL_ID_MAX_LENGTH,
)
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
    name: Mapped[str] = mapped_column(String(length=DELIVERY_LABEL_MAX_LENGTH), nullable=False)
    full_address: Mapped[str] = mapped_column(String(length=DELIVERY_ADDRESS_MAX_LENGTH), nullable=False)
    details: Mapped[str | None] = mapped_column(String(length=DELIVERY_COMMENT_MAX_LENGTH), nullable=True)
    city: Mapped[str | None] = mapped_column(String(length=DELIVERY_CITY_MAX_LENGTH), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(length=DELIVERY_POSTAL_CODE_MAX_LENGTH), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(length=EXTERNAL_ID_MAX_LENGTH), nullable=True, index=True)

    user: Mapped["User"] = relationship(back_populates="delivery_addresses")
    drafts: Mapped[list["OrderDraft"]] = relationship(back_populates="delivery_address")


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
