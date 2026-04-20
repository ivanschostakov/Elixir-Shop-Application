"""add delivery address tables

Revision ID: f31e2a4d9b0c
Revises: 7a9c4d1e2b3f
Create Date: 2026-04-18 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f31e2a4d9b0c"
down_revision: Union[str, Sequence[str], None] = "7a9c4d1e2b3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COUNTRY_CODES = (
    "RU",
    "BY",
    "KZ",
    "AZ",
    "MD",
    "AM",
    "UZ",
    "KG",
    "GE",
    "MN",
    "CN",
    "JP",
    "RS",
    "IL",
    "AE",
    "IN",
    "BD",
    "VN",
    "TH",
    "ID",
    "US",
)
DELIVERY_PROVIDERS = ("YANDEX", "CDEK")

COUNTRY_CODE_ENUM = sa.Enum(*COUNTRY_CODES, name="country_code_enum", create_type=False)
DELIVERY_PROVIDER_ENUM = sa.Enum(*DELIVERY_PROVIDERS, name="delivery_provider_enum", create_type=False)


def _create_enum_types() -> None:
    bind = op.get_bind()
    sa.Enum(*COUNTRY_CODES, name="country_code_enum").create(bind, checkfirst=True)
    sa.Enum(*DELIVERY_PROVIDERS, name="delivery_provider_enum").create(bind, checkfirst=True)


def _drop_enum_types() -> None:
    bind = op.get_bind()
    sa.Enum(*DELIVERY_PROVIDERS, name="delivery_provider_enum").drop(bind, checkfirst=True)
    sa.Enum(*COUNTRY_CODES, name="country_code_enum").drop(bind, checkfirst=True)


def _address_columns(*, include_delivery_point: bool) -> list[sa.Column]:
    columns = [
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("country_code", COUNTRY_CODE_ENUM, nullable=False),
        sa.Column("provider", DELIVERY_PROVIDER_ENUM, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("full_address", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("shipment_point", sa.String(length=255), nullable=False),
        sa.Column("comment", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
    ]
    if include_delivery_point:
        columns.append(sa.Column("delivery_point", sa.String(length=255), nullable=False))
    columns.extend(
        [
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        ]
    )
    return columns


def _create_address_table(table_name: str, *, include_delivery_point: bool) -> None:
    op.create_table(table_name, *_address_columns(include_delivery_point=include_delivery_point))
    op.create_index(op.f(f"ix_{table_name}_id"), table_name, ["id"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_user_id"), table_name, ["user_id"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_country_code"), table_name, ["country_code"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_provider"), table_name, ["provider"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_name"), table_name, ["name"], unique=False)


def _drop_address_table(table_name: str) -> None:
    op.drop_index(op.f(f"ix_{table_name}_name"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_provider"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_country_code"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_user_id"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_id"), table_name=table_name)
    op.drop_table(table_name)


def upgrade() -> None:
    _create_enum_types()

    _create_address_table("cdek_pickup_addresses", include_delivery_point=True)
    _create_address_table("yandex_pickup_addresses", include_delivery_point=True)
    _create_address_table("cdek_door_addresses", include_delivery_point=False)
    _create_address_table("yandex_door_addresses", include_delivery_point=False)


def downgrade() -> None:
    _drop_address_table("yandex_door_addresses")
    _drop_address_table("cdek_door_addresses")
    _drop_address_table("yandex_pickup_addresses")
    _drop_address_table("cdek_pickup_addresses")

    _drop_enum_types()
