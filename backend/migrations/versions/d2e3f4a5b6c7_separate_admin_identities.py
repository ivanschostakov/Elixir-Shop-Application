"""separate admin identities and sessions from customer accounts

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d2e3f4a5b6c7"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _admins_identity_fk_name() -> str:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys("admins"):
        if foreign_key["constrained_columns"] == ["user_id"]:
            name = foreign_key.get("name")
            if name:
                return str(name)
    raise RuntimeError("Foreign key for admins.user_id was not found")


def upgrade() -> None:
    op.create_table(
        "admin_identities",
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("surname", sa.String(length=100), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_admin_identities_email"),
    )
    op.create_index(
        op.f("ix_admin_identities_email"),
        "admin_identities",
        ["email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_identities_id"),
        "admin_identities",
        ["id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO admin_identities (
            id,
            email,
            password_hash,
            name,
            surname,
            is_active,
            last_active_at,
            created_at,
            updated_at
        )
        SELECT
            users.id,
            COALESCE(
                lower(users.email),
                'admin-' || users.id::text || '@invalid.local'
            ),
            users.password_hash,
            users.name,
            users.surname,
            users.is_active,
            users.last_active_at,
            users.created_at,
            users.updated_at
        FROM admins
        JOIN users ON users.id = admins.user_id
        """
    )
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('admin_identities', 'id'),
            COALESCE((SELECT max(id) FROM admin_identities), 1),
            EXISTS (SELECT 1 FROM admin_identities)
        )
        """
    )

    old_fk_name = _admins_identity_fk_name()
    op.drop_constraint(old_fk_name, "admins", type_="foreignkey")
    op.create_foreign_key(
        "fk_admins_user_id_admin_identities",
        "admins",
        "admin_identities",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "admin_sessions",
        sa.Column("admin_user_id", sa.BigInteger(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["admin_user_id"],
            ["admin_identities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_sessions_admin_user_id"),
        "admin_sessions",
        ["admin_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_sessions_id"),
        "admin_sessions",
        ["id"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO admin_sessions (
            id,
            admin_user_id,
            refresh_token_hash,
            expires_at,
            revoked_at,
            last_used_at,
            user_agent,
            ip_address,
            mfa_verified_at,
            created_at,
            updated_at
        )
        SELECT
            id,
            user_id,
            refresh_token_hash,
            expires_at,
            revoked_at,
            last_used_at,
            user_agent,
            ip_address,
            mfa_verified_at,
            created_at,
            updated_at
        FROM user_sessions
        WHERE purpose = 'admin'
        """
    )
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('admin_sessions', 'id'),
            COALESCE((SELECT max(id) FROM admin_sessions), 1),
            EXISTS (SELECT 1 FROM admin_sessions)
        )
        """
    )
    op.execute("DELETE FROM user_sessions WHERE purpose = 'admin'")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM admin_identities
                LEFT JOIN users ON users.id = admin_identities.id
                WHERE users.id IS NULL
                   OR lower(users.email) IS DISTINCT FROM lower(admin_identities.email)
                   OR users.password_hash IS DISTINCT FROM admin_identities.password_hash
                   OR users.name IS DISTINCT FROM admin_identities.name
                   OR users.surname IS DISTINCT FROM admin_identities.surname
                   OR users.is_active IS DISTINCT FROM admin_identities.is_active
            ) THEN
                RAISE EXCEPTION
                    'Cannot safely merge independent admin identities back into customer users';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM admin_sessions
                JOIN user_sessions USING (id)
            ) THEN
                RAISE EXCEPTION
                    'Cannot safely merge admin sessions because session IDs overlap';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        INSERT INTO user_sessions (
            id,
            user_id,
            refresh_token_hash,
            expires_at,
            revoked_at,
            last_used_at,
            user_agent,
            ip_address,
            purpose,
            mfa_verified_at,
            created_at,
            updated_at
        )
        SELECT
            id,
            admin_user_id,
            refresh_token_hash,
            expires_at,
            revoked_at,
            last_used_at,
            user_agent,
            ip_address,
            'admin',
            mfa_verified_at,
            created_at,
            updated_at
        FROM admin_sessions
        """
    )
    op.drop_constraint(
        "fk_admins_user_id_admin_identities",
        "admins",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "admins_user_id_fkey",
        "admins",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index(
        op.f("ix_admin_sessions_id"),
        table_name="admin_sessions",
    )
    op.drop_index(
        op.f("ix_admin_sessions_admin_user_id"),
        table_name="admin_sessions",
    )
    op.drop_table("admin_sessions")
    op.drop_index(
        op.f("ix_admin_identities_id"),
        table_name="admin_identities",
    )
    op.drop_index(
        op.f("ix_admin_identities_email"),
        table_name="admin_identities",
    )
    op.drop_table("admin_identities")
