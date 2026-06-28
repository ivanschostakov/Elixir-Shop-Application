"""phone first users drop username

Revision ID: f3c1d2e4b5a6
Revises: e2f4c6a8b1d0
Create Date: 2026-06-29 02:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f3c1d2e4b5a6"
down_revision = "e2f4c6a8b1d0"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _unique_constraint_names(inspector: sa.Inspector, table_name: str) -> set[str | None]:
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "users"):
        return

    user_columns = _column_names(inspector, "users")
    if "email" in user_columns:
        op.execute(
            sa.text(
                """
                update users
                set email = null
                where email is not null
                  and btrim(email) = ''
                """
            )
        )
        op.execute(
            sa.text(
                """
                update users
                set email = lower(btrim(email))
                where email is not null
                """
            )
        )
        op.alter_column("users", "email", existing_type=sa.String(length=100), nullable=True)

    if "phone_number" in user_columns:
        op.execute(
            sa.text(
                r"""
                update users
                set phone_number = nullif(regexp_replace(btrim(phone_number), '[\s()\-]+', '', 'g'), '')
                where phone_number is not null
                """
            )
        )
        op.execute(
            sa.text(
                """
                update users
                set phone_number = '+97' || right(lpad(id::text, 13, '0'), 13),
                    is_active = false,
                    is_verified = false
                where phone_number is null
                """
            )
        )
        op.execute(
            sa.text(
                """
                with ranked as (
                    select id, row_number() over (partition by phone_number order by id) as rn
                    from users
                    where phone_number is not null
                )
                update users as u
                set phone_number = '+97' || right(lpad(u.id::text, 13, '0'), 13),
                    is_active = false,
                    is_verified = false
                from ranked
                where ranked.id = u.id
                  and ranked.rn > 1
                """
            )
        )

    if "username" in user_columns:
        op.drop_column("users", "username")

    inspector = sa.inspect(bind)
    unique_constraints = _unique_constraint_names(inspector, "users")
    if "uq_users_phone_number" not in unique_constraints:
        op.create_unique_constraint("uq_users_phone_number", "users", ["phone_number"])
    op.alter_column("users", "phone_number", existing_type=sa.String(length=20), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "users"):
        return

    user_columns = _column_names(inspector, "users")
    unique_constraints = _unique_constraint_names(inspector, "users")

    if "uq_users_phone_number" in unique_constraints:
        op.drop_constraint("uq_users_phone_number", "users", type_="unique")
    if "phone_number" in user_columns:
        op.alter_column("users", "phone_number", existing_type=sa.String(length=20), nullable=True)

    if "username" not in user_columns:
        op.add_column("users", sa.Column("username", sa.String(length=16), nullable=True))
        op.execute(
            sa.text(
                """
                update users
                set username = left('user_' || id::text, 16)
                where username is null
                """
            )
        )
        op.alter_column("users", "username", existing_type=sa.String(length=16), nullable=False)
        op.create_unique_constraint("uq_users_username", "users", ["username"])

    if "email" in _column_names(sa.inspect(bind), "users"):
        op.execute(
            sa.text(
                """
                update users
                set email = 'deleted_' || id::text || '@example.invalid'
                where email is null
                """
            )
        )
        op.alter_column("users", "email", existing_type=sa.String(length=100), nullable=False)
