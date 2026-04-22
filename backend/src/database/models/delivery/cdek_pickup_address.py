from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import DELIVERY_POINT_MAX_LENGTH
from src.database.mixins import DeliveryAddressMixin


class CdekPickupAddress(Base, DeliveryAddressMixin):
    __tablename__ = "cdek_pickup_addresses"

    delivery_point: Mapped[str] = mapped_column(String(length=DELIVERY_POINT_MAX_LENGTH), nullable=False)

    user: Mapped["User"] = relationship(back_populates="cdek_pickup_addresses")
