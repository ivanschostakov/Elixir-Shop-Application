from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.limits import EMAIL_MAX_LENGTH, PERSON_NAME_MAX_LENGTH, WEBSITE_PHONE_MAX_LENGTH
from src.database.mixins import IdPkMixin, TimestampMixin


class DeliveryRecipient(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "delivery_recipients"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(length=PERSON_NAME_MAX_LENGTH), nullable=False)
    surname: Mapped[str] = mapped_column(String(length=PERSON_NAME_MAX_LENGTH), nullable=False)
    phone: Mapped[str] = mapped_column(String(length=WEBSITE_PHONE_MAX_LENGTH), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(length=EMAIL_MAX_LENGTH), nullable=False, default="")

    user: Mapped["User"] = relationship(back_populates="delivery_recipients")
    drafts: Mapped[list["OrderDraft"]] = relationship(back_populates="recipient")
