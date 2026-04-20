import uuid
from datetime import datetime
from typing import get_args

from sqlalchemy import BigInteger, DateTime, func, ForeignKey, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from config import ufa_now
from src.database.limits import DELIVERY_ADDRESS_MAX_LENGTH, DELIVERY_LABEL_MAX_LENGTH
from src.integrations.delivery.schemas import CountryCode, DeliveryProvider


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=ufa_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=ufa_now, onupdate=ufa_now)


class IdPkMixin:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, index=True)


class SystemMixin(IdPkMixin, TimestampMixin):
    system_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)


def _literal_values(type_alias: object) -> tuple[str, ...]:
    return get_args(getattr(type_alias, "__value__", type_alias))


COUNTRY_CODE_DB_ENUM = Enum(*_literal_values(CountryCode), name="country_code_enum")
DELIVERY_PROVIDER_DB_ENUM = Enum(*_literal_values(DeliveryProvider), name="delivery_provider_enum")


class DeliveryAddressMixin(IdPkMixin, TimestampMixin):
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), index=True, nullable=False)
    country_code: Mapped[CountryCode] = mapped_column(COUNTRY_CODE_DB_ENUM, index=True, nullable=False)
    provider: Mapped[DeliveryProvider] = mapped_column(DELIVERY_PROVIDER_DB_ENUM, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(DELIVERY_LABEL_MAX_LENGTH), nullable=False, index=True)
    full_address: Mapped[str] = mapped_column(String(DELIVERY_ADDRESS_MAX_LENGTH), nullable=False)
