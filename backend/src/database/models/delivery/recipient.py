from sqlalchemy import BigInteger, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from src.database import Base
from src.database.limits import EMAIL_MAX_LENGTH, PERSON_NAME_MAX_LENGTH, WEBSITE_PHONE_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin
from src.normalize import normalize_person_name


class DeliveryRecipient(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "delivery_recipients"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(length=PERSON_NAME_MAX_LENGTH), nullable=False)
    surname: Mapped[str] = mapped_column(String(length=PERSON_NAME_MAX_LENGTH), nullable=False)
    phone: Mapped[str] = mapped_column(String(length=WEBSITE_PHONE_MAX_LENGTH), nullable=False, default="", server_default=text("''"))
    email: Mapped[str] = mapped_column(String(length=EMAIL_MAX_LENGTH), nullable=False, default="", server_default=text("''"))

    user: Mapped["User"] = relationship(back_populates="delivery_recipients")
    baskets: Mapped[list["Basket"]] = relationship(back_populates="recipient")
    drafts: Mapped[list["OrderDraft"]] = relationship(back_populates="recipient")
    orders: Mapped[list["Order"]] = relationship(back_populates="recipient", passive_deletes="all")

    @validates("name", "surname")
    def _normalize_name_parts(self, key: str, value: str) -> str:
        normalized = normalize_person_name(value, max_length=PERSON_NAME_MAX_LENGTH)
        if normalized is None:
            raise ValueError(f"{key} must not be empty")
        return normalized
