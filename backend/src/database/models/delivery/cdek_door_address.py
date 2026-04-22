from sqlalchemy.orm import Mapped, relationship

from src.database import Base
from src.database.mixins import DeliveryAddressMixin


class CdekDoorAddress(Base, DeliveryAddressMixin):
    __tablename__ = "cdek_door_addresses"

    user: Mapped["User"] = relationship(back_populates="cdek_door_addresses")
