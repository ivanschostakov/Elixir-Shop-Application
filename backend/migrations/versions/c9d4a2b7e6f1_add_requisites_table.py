"""add requisites table

Revision ID: c9d4a2b7e6f1
Revises: 6c1f0b8e9a72
Create Date: 2026-05-02 10:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c9d4a2b7e6f1"
down_revision: Union[str, Sequence[str], None] = "6c1f0b8e9a72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requisites",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_requisites_id"), "requisites", ["id"], unique=False)
    op.create_index(op.f("ix_requisites_created_at"), "requisites", ["created_at"], unique=False)

    requisite_table = sa.table(
        "requisites",
        sa.column("title", sa.String(length=255)),
        sa.column("config", postgresql.JSONB(astext_type=sa.Text())),
    )

    op.bulk_insert(
        requisite_table,
        [
            {
                "title": 'Товарищество с ограниченной ответственностью "Слимэликсирпептайд"',
                "config": {
                    "Юридический адрес": "Казахстан, Западно-Казахстанская область, город Уральск, ул. Некрасова, д. 29/1",
                    "Почтовый адрес": "Казахстан, Западно-Казахстанская область, город Уральск, ул. Некрасова, д. 29/1",
                    "БИН": "260340023091",
                    "Телефон": "+7 961 038 79 77",
                    "Режим работы": "Понедельник – Воскресенье, 10:00 – 20:00",
                },
            },
            {
                "title": "Индивидуальный предприниматель ХАКИМОВ РУСЛАН РАЛИФОВИЧ",
                "config": {
                    "Юридический адрес": "450150 Республика Башкортостан, г. Уфа, улица Набережная р. Уфы, 39, корп. 1, кв. 87",
                    "Почтовый адрес": "450150 Республика Башкортостан, г. Уфа, улица Набережная р. Уфы, 39, корп. 1, кв. 87",
                    "ИНН": "027614099149",
                    "ОГРНИП": "323028000061111",
                    "Телефон": "+7 961 038 79 77",
                    "Электронная почта": "elixirpeptide@yandex.ru",
                    "Банк": 'ФИЛИАЛ "НИЖЕГОРОДСКИЙ" АО"АЛЬФА-БАНК"',
                    "БИК": "042202824",
                    "Корреспондентский счет": "30101810200000000824",
                    "Расчетный счет": "40802810029300014811",
                },
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_requisites_created_at"), table_name="requisites")
    op.drop_index(op.f("ix_requisites_id"), table_name="requisites")
    op.drop_table("requisites")
