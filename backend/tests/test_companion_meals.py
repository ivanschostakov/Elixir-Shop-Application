import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from sqlalchemy import select

import config
from src.app.services.ai.companion import service
from src.app.services.ai.companion.jobs import reminder_text, schedule_recurring
from src.app.services.ai.companion.meals import eating_habits, meal_type, water_target
from src.app.services.ai.companion.schemas import Action, EntryData, Nutrition, ProfileData, Settings
from src.database.models.ai.companion import AICompanionReminder
from test_ai_companion_db import URL, act, database, enable

NOW = datetime(2030, 1, 10, 9, 15, tzinfo=timezone.utc)
db_test = pytest.mark.skipif(not URL, reason="Needs isolated companion_test DB")


def meal(at=NOW, **values):
    return EntryData(kind="meal", occurred_at=at, name="Chicken", nutrition=Nutrition(kcal=1270, protein=90, fat=50, carbs=115), **values)


def test_water_and_meal_metadata_are_typed_and_cannot_leak_to_other_records():
    assert len(meal(note="x" * 4000).note) == 4000
    with pytest.raises(ValidationError):
        meal(note="x" * 4001)
    assert EntryData(kind="water", occurred_at=NOW, water_ml=250).water_ml == 250
    for payload in ({"kind": "water"}, {"kind": "water", "water_ml": 0}, {"kind": "water", "water_ml": 250, "meal_type": "breakfast"}, {"kind": "weight", "weight_kg": 80, "water_ml": 250}):
        with pytest.raises(ValidationError):
            EntryData(occurred_at=NOW, **payload)
    with pytest.raises(ValidationError):
        meal(meal_type="breakfast", meal_key="group")
    with pytest.raises(ValidationError):
        meal(food_photo_attachment_ids=[1, 1])
    profile = SimpleNamespace(settings={}, data={"sex": "female"})
    assert water_target(profile) == 1600
    profile.data["sex"] = "male"
    assert water_target(profile) == 2000
    profile.settings["water_goal_ml"] = 1800
    assert water_target(profile) == 1800


def test_habits_count_local_days_not_dishes_and_exclude_today_and_extra_meals():
    zone = ZoneInfo("UTC")
    rows = []
    for day in (1, 2, 3):
        at = (NOW - timedelta(days=day)).replace(hour=8, minute=day)
        rows.append(SimpleNamespace(id=day, occurred_at=at, data={"meal_type": "breakfast"}))
    for i in range(10):
        rows.append(SimpleNamespace(id=100+i, occurred_at=(NOW-timedelta(days=1)).replace(hour=10, minute=i), data={"meal_type": "breakfast"}))
        rows.append(SimpleNamespace(id=200+i, occurred_at=(NOW-timedelta(days=1)).replace(hour=9, minute=i), data={"meal_type": "extra"}))
    rows.append(SimpleNamespace(id=300, occurred_at=NOW, data={"meal_type": "breakfast"}))
    habits = eating_habits(rows, zone, NOW.date())
    assert habits["breakfast"] == {"time": "08:00", "days": 3}
    assert habits["lunch"] == {"time": None, "days": 0}
    assert meal_type(SimpleNamespace(data={}, occurred_at=NOW.replace(hour=14)), zone) == "lunch"


@db_test
def test_action_response_updates_all_totals_immediately_with_fast_device_clock(monkeypatch):
    from src.app.modules.users.me.companion import action
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    monkeypatch.setattr(service, "now_utc", lambda: NOW)
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            await act(db, user, "settings", expected_version=profile.version, settings=Settings(timezone="UTC"))
            await act(db, user, "entry", entry=EntryData(kind="weight", occurred_at=NOW, weight_kg=80))
            await act(db, user, "profile", expected_version=profile.version, profile=ProfileData(goal="maintain", age=30, sex="male", height_cm=180, activity="low", nutrition=Nutrition(kcal=3069, protein=191.8, fat=102.3, carbs=345.3)))
            request = SimpleNamespace(headers={})
            payload = Action(request_key="meal-clock-save", kind="entry", record_now=True, entry=meal(NOW+timedelta(minutes=3), meal_type="lunch"))
            saved = (await action(payload, request, user, db))["state"]
            assert saved["today"]["nutrition"]["kcal"] == "1270"
            assert saved["mentor"]["today"]["nutrition"]["consumed"]["kcal"] == "1270"
            assert saved["mentor"]["today"]["nutrition"]["remaining"]["kcal"] == "1799"
            row = next(row for row in saved["entries"] if row["kind"] == "meal")
            assert datetime.fromisoformat(row["occurred_at"]) == NOW
            water = Action(request_key="water-clock-save", kind="entry", record_now=True, entry=EntryData(kind="water", occurred_at=NOW+timedelta(days=1), water_ml=250))
            updated = (await action(water, request, user, db))["state"]
            assert water.entry.occurred_at == NOW + timedelta(days=1)
            repeated = (await action(water, request, user, db))["state"]
            assert repeated["today"]["water_ml"] == 250
            assert updated["today"]["water_ml"] == 250
            assert updated["mentor"]["today"]["water"] == {"consumed_ml": 250, "target_ml": 2000}
            assert updated["today"]["nutrition"]["kcal"] == "1270"
            replacement = meal(meal_type="dinner"); replacement.nutrition.kcal = Decimal(500)
            changed = (await action(Action(request_key="meal-clock-edit", kind="entry", resource_id=row["id"], expected_version=row["version"], entry=replacement), request, user, db))["state"]
            assert changed["mentor"]["today"]["nutrition"]["consumed"]["kcal"] == "500"
            changed_row = next(row for row in changed["entries"] if row["kind"] == "meal")
            deleted = (await action(Action(request_key="meal-clock-delete", kind="delete_entry", resource_id=changed_row["id"], expected_version=changed_row["version"]), request, user, db))["state"]
            assert deleted["mentor"]["today"]["nutrition"]["consumed"]["kcal"] == "0"
            assert deleted["mentor"]["today"]["water"]["consumed_ml"] == 250
            # Existing installed clients without record_now also tolerate clock skew.
            legacy = (await action(Action(request_key="meal-old-client", kind="entry", entry=meal(NOW+timedelta(minutes=2))), request, user, db))["state"]
            assert legacy["mentor"]["today"]["nutrition"]["consumed"]["kcal"] == "1270"
    asyncio.run(run())


@db_test
def test_meal_reminder_deduplicates_and_rechecks_food_before_delivery(monkeypatch):
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    monkeypatch.setattr(service, "now_utc", lambda: NOW)
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            await act(db, user, "settings", expected_version=profile.version, settings=Settings(timezone="UTC", meal_reminders=["breakfast"]))
            for day in (1, 2, 3):
                await act(db, user, "entry", entry=meal((NOW-timedelta(days=day)).replace(hour=8, minute=day), meal_type="breakfast"))
            await schedule_recurring(db, profile, NOW); await db.flush()
            await schedule_recurring(db, profile, NOW); await db.flush()
            rows = list((await db.execute(select(AICompanionReminder).where(AICompanionReminder.kind == "meal_breakfast"))).scalars())
            assert len(rows) == 1 and rows[0].due_at.hour == 8 and rows[0].due_at.minute == 30
            assert "завтрак" in await reminder_text(db, rows[0], profile)
            await act(db, user, "entry", entry=meal(meal_type="breakfast"))
            assert await reminder_text(db, rows[0], profile) is None
            await act(db, user, "settings", expected_version=profile.version, settings=Settings(timezone="UTC", meal_reminders=[]))
            assert await reminder_text(db, rows[0], profile) is None
    asyncio.run(run())
