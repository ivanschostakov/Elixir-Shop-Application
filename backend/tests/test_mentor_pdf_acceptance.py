import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from test_ai_companion_db import URL, database
from src.app.modules.telegram_ai import mentor as m, journal as j, profile as p, reminders as r
from src.app.modules.telegram_ai.course_inventory import normalize_supply, calculate_supply
from src.database.models import TelegramAIJournal

UID = 88000001993
NOW = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)


def course(**changes):
    return dict(name="Existing scheme", dose_text="User-reported 2 mg per intake", source="user",
        start_date="2030-01-01", end_date="2030-02-01", weekdays=[1], times=["09:00"], timezone="UTC",
        **changes)


def test_package_contents_are_distinct_from_count_and_consumption():
    value = m.Course.model_validate(course(package_count=1, package_amount=10, package_unit="mg",
        amount_per_intake=2, intake_unit="mg"))
    assert value.supply_amount == 10 and value.amount_per_intake == 2 and value.supply_unit == "мг"
    assert value.dose_text == "User-reported 2 mg per intake"
    assert m.Course.model_validate(value.model_dump()).model_dump() == value.model_dump()


def test_explicit_mass_conversion_is_applied_only_once():
    value = m.Course.model_validate(course(package_count=1, package_amount=10, package_unit="mg",
        amount_per_intake=0.002, intake_unit="g"))
    assert value.amount_per_intake == 2
    assert m.Course.model_validate(value.model_dump()).amount_per_intake == 2


@pytest.mark.parametrize("values", [
    dict(supply_amount=1, amount_per_intake=2, supply_unit="флакон 10 мг"),
    dict(package_count=1, amount_per_intake=2, intake_unit="мг"),
    dict(supply_amount=10, supply_unit="мл", amount_per_intake=2, intake_unit="мг"),
    dict(package_count=1, package_amount=10, package_unit="mg", supply_amount=1,
        supply_unit="mg", amount_per_intake=2, intake_unit="mg"),
])
def test_ambiguous_supply_cannot_create_a_confident_prediction(values):
    with pytest.raises((ValueError, ValidationError)):
        m.Course.model_validate(course(**values))


def test_inventory_baseline_excludes_old_intakes_even_at_the_same_timestamp():
    scheme = SimpleNamespace(occurred_at=NOW, data={"supply_amount": 10, "amount_per_intake": 2,
        "supply_unit": "мг", "supply_baseline_done": [1], "supply_measured_at": NOW.isoformat()})
    events = [SimpleNamespace(id=1, status="done", occurred_at=NOW, data={"completed_at": NOW.isoformat()}),
        *[SimpleNamespace(id=i+2, status="pending", occurred_at=NOW+timedelta(days=i+1), data={}) for i in range(6)]]
    result = calculate_supply(scheme, events, NOW)
    assert result["remaining"] == 10 and result["intakes_available"] == 5
    assert result["runs_out_at"] == (NOW+timedelta(days=6)).isoformat()
    events[1].status = "done"
    events[1].data["completed_at"] = NOW.isoformat()
    assert calculate_supply(scheme, events, NOW)["remaining"] == 8


def test_month_mean_is_not_a_relabelled_seven_day_mean():
    rows = [SimpleNamespace(id=i, kind="weight", status="confirmed", occurred_at=NOW-timedelta(days=days),
        data={"weight_kg": value}) for i, (days, value) in enumerate([(20, 90), (3, 82), (1, 80)])]
    month = m.summarize(rows, NOW, ZoneInfo("UTC"), 30)
    assert month["weight_mean"] == 84 and month["weight_samples"] == 3
    assert month["weight_mean_7d"] == 81


@pytest.mark.skipif(not URL, reason="Requires isolated companion_test database")
def test_real_course_count_stock_update_and_duplicate_confirmation(monkeypatch):
    monkeypatch.setattr(m, "now", lambda: NOW)
    monkeypatch.setattr(j, "now", lambda: NOW)
    async def run():
        async with database() as (db, _):
            result = await m.record_draft(m.RecordDraft(telegram_user_id=UID, request_key="pdf-course-create",
                kind="course", data=course(package_count=1, package_amount=10, package_unit="mg",
                    amount_per_intake=2, intake_unit="mg")), db)
            cid = result["entry"]["id"]
            await m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=cid, action="confirm"), db)
            await m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=cid, action="confirm"), db)
            before = await m.workspace_state(db, UID)
            assert before["courses"][0]["supply"]["intakes_available"] == 5
            events = list((await db.execute(select(TelegramAIJournal).where(
                TelegramAIJournal.kind == "course_event", TelegramAIJournal.telegram_user_id == UID
            ).order_by(TelegramAIJournal.occurred_at))).scalars())
            assert len(events) == 5
            await m.course_action(m.CourseAction(telegram_user_id=UID, entry_id=events[0].id, action="done"), db)
            assert (await m.workspace_state(db, UID))["courses"][0]["supply"]["remaining"] == 8
            update = m.CourseSupply(telegram_user_id=UID, entry_id=cid, request_key="pdf-stock-measured",
                supply_amount=6, amount_per_intake=2, supply_unit="mg")
            await m.course_supply(update, db)
            assert (await m.workspace_state(db, UID))["courses"][0]["supply"]["intakes_available"] == 3
            later = m.CourseSupply(**{**update.model_dump(), "request_key": "pdf-stock-newer", "supply_amount": 10})
            await m.course_supply(later, db)
            await m.course_supply(update, db)
            assert (await m.workspace_state(db, UID))["courses"][0]["supply"]["remaining"] == 10
            assert (await m.read_record(m.RecordRead(telegram_user_id=UID, entry_id=cid), db))["entry"]["dose_text"] == course()["dose_text"]
            with pytest.raises(HTTPException) as error:
                await m.course_supply(m.CourseSupply(**{**update.model_dump(), "telegram_user_id": UID+1}), db)
            assert error.value.status_code == 404
    asyncio.run(run())


@pytest.mark.skipif(not URL, reason="Requires isolated companion_test database")
def test_food_estimate_does_not_affect_diary_and_delete_recalculates_it():
    async def run():
        async with database() as (db, _):
            payload = j.MealDraft(telegram_user_id=UID, request_key="pdf-lookup-food", meal={
                "name": "Reference meal", "kcal": 242, "protein": 34, "fat": 10, "carbs": 6})
            estimate = (await m.estimate_food(payload, db))["estimate"]
            assert (await j.dashboard(p.Identity(telegram_user_id=UID), db))["totals"]["kcal"] == 0
            assert (await m.meals(m.MealLibrary(telegram_user_id=UID), db))["items"] == []
            with pytest.raises(HTTPException) as error:
                await m.record_estimate(m.EstimateRecord(telegram_user_id=UID+1, entry_id=estimate["id"]), db)
            assert error.value.status_code == 404
            action = m.EstimateRecord(telegram_user_id=UID, entry_id=estimate["id"])
            first = (await m.record_estimate(action, db))["entry"]
            assert (await m.record_estimate(action, db))["entry"]["id"] == first["id"]
            assert (await j.dashboard(p.Identity(telegram_user_id=UID), db))["totals"]["kcal"] == 242
            await m.delete_meal(m.EstimateRecord(telegram_user_id=UID, entry_id=first["id"]), db)
            await m.delete_meal(m.EstimateRecord(telegram_user_id=UID, entry_id=first["id"]), db)
            assert (await j.dashboard(p.Identity(telegram_user_id=UID), db))["totals"]["kcal"] == 0
            with pytest.raises(HTTPException):
                await m.record_estimate(action, db)
    asyncio.run(run())


@pytest.mark.skipif(not URL, reason="Requires isolated companion_test database")
def test_timezone_and_nutrition_saving_work_with_new_profile(monkeypatch):
    async def run():
        async with database() as (db, _):
            await p.update(p.Update(telegram_user_id=UID, expected_version=0, request_key="pdf-profile",
                source_text="I am a 35-year-old man, 180 cm, 80 kg; maintain weight, moderately active",
                evidence="I am a 35-year-old man, 180 cm, 80 kg; maintain weight, moderately active",
                patch={"goal": "maintain", "age": 35, "sex": "male", "height_cm": 180,
                    "current_weight_kg": 80, "activity": "moderate"}), db)
            await r.options(r.Options(telegram_user_id=UID, timezone="Asia/Almaty", morning="08:00"), db)
            data = await j.dashboard(p.Identity(telegram_user_id=UID), db)
            assert data["settings"]["timezone"] == data["settings"]["reminders"]["timezone"] == "Asia/Almaty"
            value = await m.nutrition_preview(m.NutritionPreview(telegram_user_id=UID, eligibility_confirmed=True), db)
            assert value["available"]
            result = await m.record_draft(m.RecordDraft(telegram_user_id=UID, request_key="pdf-target",
                kind="target", data={**value["nutrition"], "source": "user"}), db)
            assert (await m.workspace_state(db, UID))["target"] is None
            await m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=result["entry"]["id"], action="confirm"), db)
            assert (await m.workspace_state(db, UID))["target"]["kcal"] == float(value["nutrition"]["kcal"])
    asyncio.run(run())


@pytest.mark.skipif(not URL, reason="Requires isolated companion_test database")
def test_old_course_events_are_reachable_markable_and_owner_scoped(monkeypatch):
    monkeypatch.setattr(m, "now", lambda: NOW)
    async def run():
        async with database() as (db, _):
            value = {**course(), "start_date": (NOW-timedelta(days=60)).date().isoformat(),
                "end_date": (NOW+timedelta(days=30)).date().isoformat(), "weekdays": [],
                "interval_days": 1, "times": ["08:00", "20:00"]}
            entry = (await m.record_draft(m.RecordDraft(telegram_user_id=UID, request_key="old-events-test",
                kind="course", data=value), db))["entry"]
            await m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=entry["id"], action="confirm"), db)
            ids = []
            for offset in range(0, 200, 20):
                page = await m.course_events(m.CourseEvents(telegram_user_id=UID, entry_id=entry["id"],
                    offset=offset, limit=20), db)
                ids.extend(row["id"] for row in page["items"])
                if not page["has_more"]:
                    break
            assert len(ids) == len(set(ids)) == 182
            pending = await m.course_events(m.CourseEvents(telegram_user_id=UID, entry_id=entry["id"], pending_only=True), db)
            oldest = pending["items"][0]
            assert datetime.fromisoformat(oldest["occurred_at"]) < NOW-timedelta(days=7)
            await m.course_action(m.CourseAction(telegram_user_id=UID, entry_id=oldest["id"], action="done"), db)
            pending = await m.course_events(m.CourseEvents(telegram_user_id=UID, entry_id=entry["id"], pending_only=True), db)
            assert oldest["id"] not in [row["id"] for row in pending["items"]]
            assert all(datetime.fromisoformat(row["occurred_at"]) <= NOW for row in pending["items"])
            state = await m.workspace_state(db, UID)
            assert state["courses"][0]["next_event"]["occurred_at"] == NOW.replace(hour=20).isoformat()
            with pytest.raises(HTTPException) as error:
                await m.course_events(m.CourseEvents(telegram_user_id=UID+1, entry_id=entry["id"]), db)
            assert error.value.status_code == 404
    asyncio.run(run())
