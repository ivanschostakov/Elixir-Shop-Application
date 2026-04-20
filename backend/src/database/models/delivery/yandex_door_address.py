from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import DELIVERY_COMMENT_MAX_LENGTH, DELIVERY_POINT_MAX_LENGTH, EMAIL_MAX_LENGTH, PERSON_NAME_MAX_LENGTH, PHONE_NUMBER_MAX_LENGTH
from src.database.mixins import DeliveryAddressMixin


class YandexDoorAddress(Base, DeliveryAddressMixin):
    __tablename__ = "yandex_door_addresses"

    full_name: Mapped[str] = mapped_column(String(length=PERSON_NAME_MAX_LENGTH), nullable=False)
    shipment_point: Mapped[str] = mapped_column(String(length=DELIVERY_POINT_MAX_LENGTH), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(length=DELIVERY_COMMENT_MAX_LENGTH), nullable=True)
    phone: Mapped[str] = mapped_column(String(length=PHONE_NUMBER_MAX_LENGTH), nullable=False)
    email: Mapped[str] = mapped_column(String(length=EMAIL_MAX_LENGTH), nullable=False)

    user: Mapped["User"] = relationship(back_populates="yandex_door_addresses")
