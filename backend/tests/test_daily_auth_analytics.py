import csv
import io
from datetime import date, datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from config import ASYNC_DB_URL
from src.app.services.admin import analytics
from src.app.services.auth import events
from src.database import Base
from src.database.models import User, UserDevice, UserEvent


def test_custom_period_checks_both_bounds(monkeypatch):
    now = datetime(2026, 11, 26, 1, tzinfo=ZoneInfo("Asia/Yekaterinburg"))
    monkeypatch.setattr(analytics, "ufa_now", lambda: now)
    today, yesterday = now.date(), date(2026, 11, 25)
    start, end = analytics.analytics_period(30, yesterday, yesterday)
    assert start.isoformat() == "2026-11-25T00:00:00+05:00"
    assert end.isoformat() == "2026-11-25T23:59:59.999999+05:00"
    assert analytics.analytics_period(30, today, today)[1] == now
    for bounds in [(today, None), (None, today), (today, yesterday),
                   (date(2025, 11, 26), today), (today, date(2026, 11, 27))]:
        with pytest.raises(HTTPException) as exc:
            analytics.analytics_period(30, *bounds)
        assert exc.value.status_code == 422


@pytest.mark.anyio
async def test_daily_auth_counts_in_postgres(monkeypatch):
    engine = create_async_engine(ASYNC_DB_URL)
    schema = "auth_analytics_" + uuid4().hex
    try:
        async with engine.connect() as conn:
            # Private schema and all test data are rolled back when the connection closes.
            await conn.execute(text(f"CREATE SCHEMA {schema}"))
            await conn.execute(text(f"SET LOCAL search_path TO {schema}"))
            await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[
                User.__table__, UserDevice.__table__, UserEvent.__table__,
            ]))
            async with AsyncSession(bind=conn) as db:
                tz = ZoneInfo("Asia/Yekaterinburg")
                start = datetime(2026, 10, 30, tzinfo=tz)
                end = datetime(2026, 11, 2, 23, 59, 59, tzinfo=tz)
                assert all(row["logins"] is None for row in await analytics.daily_auth_counts(db, start, end))
                user = User(name="Test", surname="Account", password_hash="unused")
                db.add(user)
                await db.flush()
                now = datetime(2026, 10, 31, 18, 59, tzinfo=timezone.utc)
                monkeypatch.setattr(events, "ufa_now", lambda: now)
                await events.record_auth_event(db, user.id, registration=True)
                now = now.replace(hour=19, minute=0)
                await events.record_auth_event(db, user.id, registration=True)
                await events.record_auth_event(db, user.id, registration=False)
                await events.record_auth_event(db, user.id, registration=False)
                db.add(UserEvent(user_id=user.id, event_name="app_opened", source="app", occurred_at=now))
                await db.flush()
                daily = await analytics.daily_auth_counts(db, start, end)
                assert [(r["registrations"], r["logins"]) for r in daily] == [
                    (None, None), (1, 0), (0, 2), (0, 0),
                ]
                csv_data = analytics.analytics_csv("customers", {"customers": {
                    "auth_daily": daily, "app_opens": {"daily": [{"period": date(2026, 11, 1), "opens": 1, "customers": 1}]},
                }})
                rows = list(csv.reader(io.StringIO(csv_data.decode("utf-8-sig"))))
                assert rows[1][3:] == ["", ""]
                assert rows[3] == ["2026-11-01", "1", "1", "0", "2"]
                assert rows[4][3:] == ["0", "0"]
    finally:
        await engine.dispose()
