"""create delivery recipients and link order drafts

Revision ID: b8c2a41f6d90
Revises: e4a8f7c1d2b4
Create Date: 2026-04-20 23:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b8c2a41f6d90"
down_revision: Union[str, Sequence[str], None] = "e4a8f7c1d2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _split_recipient_name(full_name: str | None, fallback_name: str | None, fallback_surname: str | None) -> tuple[str, str]:
    normalized_full_name = (full_name or "").strip()
    normalized_fallback_name = (fallback_name or "").strip() or "Покупатель"
    normalized_fallback_surname = (fallback_surname or "").strip() or "Получатель"

    if not normalized_full_name:
        return normalized_fallback_name, normalized_fallback_surname

    parts = normalized_full_name.split()
    name = parts[0] if parts else normalized_fallback_name
    surname = " ".join(parts[1:]).strip() or normalized_fallback_surname
    return name, surname


def _has_recipient_data(full_name: str | None, phone: str | None, email: str | None) -> bool:
    return any((value or "").strip() for value in (full_name, phone, email))


def upgrade() -> None:
    op.create_table(
        "delivery_recipients",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("surname", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_delivery_recipients_id"), "delivery_recipients", ["id"], unique=False)
    op.create_index(op.f("ix_delivery_recipients_user_id"), "delivery_recipients", ["user_id"], unique=False)

    op.alter_column("delivery_recipients", "phone", server_default=None)
    op.alter_column("delivery_recipients", "email", server_default=None)

    op.add_column("order_drafts", sa.Column("recipient_id", sa.BigInteger(), nullable=True))
    op.create_index(op.f("ix_order_drafts_recipient_id"), "order_drafts", ["recipient_id"], unique=False)
    op.create_foreign_key(
        "fk_order_drafts_recipient_id_delivery_recipients",
        "order_drafts",
        "delivery_recipients",
        ["recipient_id"],
        ["id"],
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT
                order_drafts.id AS draft_id,
                order_drafts.user_id AS user_id,
                order_drafts.recipient_name AS recipient_name,
                order_drafts.recipient_phone AS recipient_phone,
                order_drafts.recipient_email AS recipient_email,
                users.name AS user_name,
                users.surname AS user_surname,
                users.phone_number AS user_phone,
                users.email AS user_email
            FROM order_drafts
            JOIN users ON users.id = order_drafts.user_id
            ORDER BY order_drafts.id
            """
        )
    ).mappings()

    recipient_cache: dict[tuple[int, str, str, str, str], int] = {}
    for row in rows:
        if not _has_recipient_data(row["recipient_name"], row["recipient_phone"], row["recipient_email"]):
            continue

        name, surname = _split_recipient_name(
            row["recipient_name"],
            row["user_name"],
            row["user_surname"],
        )
        phone = (row["recipient_phone"] or row["user_phone"] or "").strip()
        email = (row["recipient_email"] or row["user_email"] or "").strip()
        cache_key = (row["user_id"], name, surname, phone, email)

        recipient_id = recipient_cache.get(cache_key)
        if recipient_id is None:
            recipient_id = bind.execute(
                sa.text(
                    """
                    INSERT INTO delivery_recipients (
                        user_id,
                        name,
                        surname,
                        phone,
                        email,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :user_id,
                        :name,
                        :surname,
                        :phone,
                        :email,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    RETURNING id
                    """
                ),
                {
                    "user_id": row["user_id"],
                    "name": name,
                    "surname": surname,
                    "phone": phone,
                    "email": email,
                },
            ).scalar_one()
            recipient_cache[cache_key] = recipient_id

        bind.execute(
            sa.text(
                """
                UPDATE order_drafts
                SET recipient_id = :recipient_id
                WHERE id = :draft_id
                """
            ),
            {"recipient_id": recipient_id, "draft_id": row["draft_id"]},
        )

    op.drop_column("order_drafts", "recipient_email")
    op.drop_column("order_drafts", "recipient_phone")
    op.drop_column("order_drafts", "recipient_name")


def downgrade() -> None:
    op.add_column("order_drafts", sa.Column("recipient_name", sa.String(length=100), nullable=True))
    op.add_column("order_drafts", sa.Column("recipient_phone", sa.String(length=80), nullable=True))
    op.add_column("order_drafts", sa.Column("recipient_email", sa.String(length=100), nullable=True))

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE order_drafts
            SET
                recipient_name = TRIM(CONCAT(delivery_recipients.name, ' ', delivery_recipients.surname)),
                recipient_phone = delivery_recipients.phone,
                recipient_email = delivery_recipients.email
            FROM delivery_recipients
            WHERE delivery_recipients.id = order_drafts.recipient_id
            """
        )
    )

    op.drop_constraint("fk_order_drafts_recipient_id_delivery_recipients", "order_drafts", type_="foreignkey")
    op.drop_index(op.f("ix_order_drafts_recipient_id"), table_name="order_drafts")
    op.drop_column("order_drafts", "recipient_id")

    op.drop_index(op.f("ix_delivery_recipients_user_id"), table_name="delivery_recipients")
    op.drop_index(op.f("ix_delivery_recipients_id"), table_name="delivery_recipients")
    op.drop_table("delivery_recipients")
