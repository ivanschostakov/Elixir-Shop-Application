"""add unique index for delivery addresses

Revision ID: 4c8e2f6a1b9d
Revises: f6a3c2d1b4e5
Create Date: 2026-04-22 15:25:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4c8e2f6a1b9d"
down_revision: Union[str, None] = "f6a3c2d1b4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEDUPLICATE_DELIVERY_ADDRESSES_SQL = """
WITH ranked AS (
    SELECT
        id,
        first_value(id) OVER (
            PARTITION BY
                user_id,
                mode,
                provider,
                country_code,
                full_address,
                COALESCE(details, ''),
                COALESCE(city, ''),
                COALESCE(postal_code, ''),
                COALESCE(provider_reference, '')
            ORDER BY id ASC
        ) AS keep_id,
        row_number() OVER (
            PARTITION BY
                user_id,
                mode,
                provider,
                country_code,
                full_address,
                COALESCE(details, ''),
                COALESCE(city, ''),
                COALESCE(postal_code, ''),
                COALESCE(provider_reference, '')
            ORDER BY id ASC
        ) AS row_num
    FROM delivery_addresses
)
UPDATE order_drafts AS draft
SET delivery_address_id = ranked.keep_id
FROM ranked
WHERE draft.delivery_address_id = ranked.id
  AND ranked.row_num > 1;
"""


DELETE_DUPLICATE_DELIVERY_ADDRESSES_SQL = """
DELETE FROM delivery_addresses AS address
USING (
    SELECT id
    FROM (
        SELECT
            id,
            row_number() OVER (
                PARTITION BY
                    user_id,
                    mode,
                    provider,
                    country_code,
                    full_address,
                    COALESCE(details, ''),
                    COALESCE(city, ''),
                    COALESCE(postal_code, ''),
                    COALESCE(provider_reference, '')
                ORDER BY id ASC
            ) AS row_num
        FROM delivery_addresses
    ) AS ranked
    WHERE ranked.row_num > 1
) AS duplicates
WHERE address.id = duplicates.id;
"""


CREATE_UNIQUE_INDEX_SQL = """
CREATE UNIQUE INDEX uq_delivery_addresses_user_identity
ON delivery_addresses (
    user_id,
    mode,
    provider,
    country_code,
    full_address,
    COALESCE(details, ''),
    COALESCE(city, ''),
    COALESCE(postal_code, ''),
    COALESCE(provider_reference, '')
);
"""


def upgrade() -> None:
    op.execute(DEDUPLICATE_DELIVERY_ADDRESSES_SQL)
    op.execute(DELETE_DUPLICATE_DELIVERY_ADDRESSES_SQL)
    op.execute(CREATE_UNIQUE_INDEX_SQL)


def downgrade() -> None:
    op.drop_index("uq_delivery_addresses_user_identity", table_name="delivery_addresses")
