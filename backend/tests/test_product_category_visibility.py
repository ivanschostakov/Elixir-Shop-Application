import pytest
from sqlalchemy.dialects import postgresql

from src.database.crud.catalog.product_category import get_product_categories


class EmptyResult:
    def scalars(self):
        return self

    def all(self):
        return []


class CapturingSession:
    statement = None

    async def execute(self, statement):
        self.statement = statement
        return EmptyResult()


@pytest.mark.anyio
async def test_public_categories_filter_hidden_and_follow_app_order():
    session = CapturingSession()

    await get_product_categories(session, sort="app_order")

    sql = str(
        session.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "product_categories.archived IS false" in sql
    assert "product_categories.is_visible_in_app IS true" in sql
    assert "ORDER BY product_categories.app_display_order ASC" in sql


@pytest.mark.anyio
async def test_internal_category_query_can_include_hidden_categories():
    session = CapturingSession()

    await get_product_categories(
        session,
        sort="app_order",
        include_archived=True,
        include_hidden=True,
    )

    sql = str(
        session.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "product_categories.archived IS false" not in sql
    assert "product_categories.is_visible_in_app IS true" not in sql
    assert "ORDER BY product_categories.app_display_order ASC" in sql
