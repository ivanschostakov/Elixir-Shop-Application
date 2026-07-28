import asyncio
from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql

from src.app.services.admin.abandoned_baskets import count_abandoned_baskets


class _Result:
    def scalar_one(self):
        return 2


class _Session:
    statement = None

    async def execute(self, statement):
        self.statement = statement
        return _Result()


def test_abandoned_basket_count_uses_non_empty_baskets_and_reporting_period():
    session = _Session()
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    end = datetime(2026, 7, 28, tzinfo=timezone.utc)

    result = asyncio.run(count_abandoned_baskets(session, start=start, end=end))
    sql = str(
        session.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert result == 2
    assert "JOIN basket_items" in sql
    assert "baskets.updated_at >= '2026-07-01" in sql
    assert "baskets.updated_at <= '2026-07-27" in sql
