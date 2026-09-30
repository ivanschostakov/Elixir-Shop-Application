import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from src.app.services.ai.companion import service
from src.app.services.ai.companion.schemas import EntryData, Nutrition
from src.database.models import User
from test_ai_companion_db import URL, act, database, enable


def test_favorites_query_is_scoped_all_time_and_reports_limit(monkeypatch):
    async def run():
        monkeypatch.setattr(service, "profile_for", AsyncMock(return_value=SimpleNamespace(enabled=True)))
        consent = AsyncMock()
        monkeypatch.setattr(service, "require_consent", consent)
        monkeypatch.setattr(service, "dump", lambda row: row)
        result = Mock()
        result.scalars.return_value = [{"id": i} for i in range(201)]
        db = SimpleNamespace(execute=AsyncMock(return_value=result))
        response = await service.favorite_meals_for(db, 42)
        assert len(response["entries"]) == 200 and response["may_have_more"] and response["limit"] == 200
        consent.assert_awaited_once_with(db, 42)
        query = db.execute.call_args.args[0].compile(dialect=postgresql.dialect())
        sql = str(query)
        assert "user_id =" in sql and "kind =" in sql and "IS true" in sql
        assert "occurred_at <=" in sql and "occurred_at >=" not in sql
        assert "occurred_at DESC" in sql and "id DESC" in sql
        assert 42 in query.params.values() and "meal" in query.params.values() and "favorite" in query.params.values()
    asyncio.run(run())


@pytest.mark.parametrize("profile", [None, SimpleNamespace(enabled=False)])
def test_favorites_disabled_profile_cannot_read(monkeypatch, profile):
    async def run():
        monkeypatch.setattr(service, "profile_for", AsyncMock(return_value=profile))
        db = SimpleNamespace(execute=AsyncMock())
        with pytest.raises(HTTPException) as error:
            await service.favorite_meals_for(db, 42)
        assert error.value.status_code == 403
        db.execute.assert_not_awaited()
    asyncio.run(run())


def test_favorites_require_current_consent(monkeypatch):
    async def run():
        monkeypatch.setattr(service, "profile_for", AsyncMock(return_value=SimpleNamespace(enabled=True)))
        monkeypatch.setattr(service, "require_consent", AsyncMock(side_effect=HTTPException(409, "Consent required")))
        db = SimpleNamespace(execute=AsyncMock())
        with pytest.raises(HTTPException) as error:
            await service.favorite_meals_for(db, 42)
        assert error.value.status_code == 409
        db.execute.assert_not_awaited()
    asyncio.run(run())


@pytest.mark.skipif(not URL, reason="Needs isolated companion_test DB")
def test_old_favorites_are_returned_but_other_users_and_future_meals_are_not():
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            now = datetime.now(timezone.utc)
            def meal(at, favorite):
                return EntryData(kind="meal", name="Favorite", occurred_at=at, favorite=favorite, nutrition=Nutrition(kcal=100, protein=5, fat=4, carbs=12))
            await act(db, user, "entry", entry=meal(now - timedelta(days=365), True))
            await act(db, user, "entry", entry=meal(now, False))
            await act(db, user, "entry", entry=meal(now + timedelta(minutes=4), True))
            foreign = User(name="Other", surname="Favorites", password_hash="unused")
            db.add(foreign)
            await db.flush()
            await enable(db, foreign)
            await act(db, foreign, "entry", entry=meal(now, True))
            result = await service.favorite_meals_for(db, user.id)
            assert len(result["entries"]) == 1 and not result["may_have_more"]
            assert result["entries"][0]["occurred_at"] == (now - timedelta(days=365)).isoformat()
    asyncio.run(run())
