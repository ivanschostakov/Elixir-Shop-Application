from uuid import UUID
from sqlalchemy import UUID as SAUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import DeliveryAddressMixin


class YandexPickupAddress(Base, DeliveryAddressMixin):
    __tablename__ = "yandex_pickup_addresses"

    platform_id: Mapped[UUID] = mapped_column(SAUUID(as_uuid=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="yandex_pickup_addresses")
