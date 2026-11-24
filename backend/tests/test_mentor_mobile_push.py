import asyncio
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from src.app.services.ai.companion import mobile_push, push_actions, service
from src.app.services.ai.companion.push_rules import nutrition_notices, program_complete, wellbeing_notices, workout_notices
from src.app.services.ai.companion.schemas import EntryData, Settings, WorkoutPlan
from src.database.models import UserPushToken
from src.database.models.ai.companion import AICompanionEntry, AICompanionReminder
from test_ai_companion_db import URL, act, database, enable

zone = ZoneInfo("UTC")
now = datetime(2030, 1, 10, 13, tzinfo=timezone.utc)
day = now.date()
clock = lambda t: datetime.combine(day, t, zone)
plan_data = {"name": "План", "start_date": "2030-01-10", "end_date": "2030-01-17", "days": [
    {"key": "strength", "name": "Спина", "weekdays": [day.weekday()], "duration_minutes": 40,
     "exercises": [{"key": "pull", "name": "Тяга", "sets": 3, "target_reps": 8}]}]}
targets = {"kcal": 2100, "protein": 120, "fat": 60, "carbs": 210}
settings = Settings(timezone="UTC", meal_reminders=["lunch"], mobile={"topics": ["nutrition", "water", "meal_balance", "post_water",
    "training", "energy", "effort", "unfinished", "reschedule", "wellbeing", "stress", "bedtime", "sleep", "rest", "program"],
    "water_time": "13:00", "workout_time": "13:00", "wellbeing_time": "13:00"})
profile = SimpleNamespace(data={"nutrition": targets, "workout_plan": plan_data}, settings=settings.model_dump(mode="json"))


def row(kind, at=now, **data):
    return SimpleNamespace(id=31, kind=kind, occurred_at=at, updated_at=at, data=data)


def test_meals_group_dishes_use_one_third_cap_at_day_remaining_and_separate_water():
    def food(kind, at, protein, **extra):
        return row("meal", at, meal_type=kind, nutrition={**targets, "kcal": 100, "protein": protein}, **extra)
    breakfast = food("breakfast", clock(time(8)), 60)
    yesterday = food("lunch", now - timedelta(days=1), 15)
    def rules(rows):
        return {n.key: n for n in nutrition_notices(profile, settings, now, zone, rows, {"lunch": {"time": "12:30"}}, clock)}
    before = rules([breakfast, yesterday])
    assert before[f"meal_lunch:{day}"].due == clock(time(13))
    assert before[f"meal_lunch:{day}"].actions == ("log_meal", "repeat_meal")
    assert before[f"gap:{day}:lunch"].data["gaps"]["protein"] == 60
    after = rules([breakfast, yesterday, food("lunch", now, 16), food("lunch", now, 10)])
    assert f"meal_lunch:{day}" not in after and f"gap:{day}:lunch" not in after
    assert after[f"balance:{day}:lunch"].data["gaps"]["protein"] == 14
    filled = rules([row("meal", now, nutrition=targets, meal_type="lunch", water_ml=1980)])
    assert filled[f"water:{day}"].data["ml"] == 20
    assert f"balance:{day}:lunch" not in filled
    only_water = rules([row("meal", now, nutrition=targets, meal_type="lunch")])
    assert only_water[f"balance:{day}:lunch"].kind == "meal_water"
    assert not rules([row("water", now, water_ml=2000)]).get(f"water:{day}")


def test_workout_and_wellbeing_replacements_and_feedback():
    def workouts(rows):
        return {n.kind: n for n in workout_notices(profile, settings, now, zone, rows, clock)}
    low = row("wellbeing", energy=2, stress=4, sleep_hours=6)
    assert {"training", "move"} == set(workouts([]))
    assert {"low_energy", "move"} == set(workouts([low]))
    w = {"status": "in_progress", "name": "Тяга", "plan_day_key": "strength", "scheduled_date": day.isoformat(),
         "exercises": [{"sets": [{"completed": True}]}]}
    assert set(workouts([row("workout", workout=w)])) == {"unfinished"}
    w["status"] = "completed"
    assert set(workouts([row("workout", workout=w)])) == {"post_water", "effort"}
    w["effort"] = "hard"
    assert "effort" not in workouts([row("workout", workout=w)])
    def wellness(rows, follow=False):
        return {n.kind for n in wellbeing_notices(settings, now, zone, rows, clock, follow)}
    assert wellness([]) == {"wellbeing"}
    assert wellness([], True) == {"sleep"}
    assert wellness([low]) == {"bedtime", "stress"}
    assert "sleep" not in wellness([row("wellbeing", sleep_quality=3)], True)
    p = WorkoutPlan.model_validate(plan_data)
    assert not program_complete(p, [(day, "strength"), (day, "strength")])
    assert program_complete(p, [(day, "strength"), (day+timedelta(days=7), "strength")])


db_only = pytest.mark.skipif(not URL, reason="Needs isolated companion_test PostgreSQL")


@db_only
def test_delivery_actions_and_retries_use_the_live_slot(monkeypatch):
    from src.app.services import push_notifications as push
    monkeypatch.setattr(service, "now_utc", lambda: now)
    captured = []
    async def send(messages):
        captured.extend(messages)
        return push.ExpoPushBatchResult(frozenset(m["to"] for m in messages), frozenset(), frozenset())
    monkeypatch.setattr(push, "_send_expo_push_messages", send)
    async def run():
        async with database() as (db, user):
            p = await enable(db, user)
            await act(db, user, "settings", expected_version=p.version, settings=settings)
            p.data = {"nutrition": targets, "workout_plan": plan_data}
            db.add(UserPushToken(user_id=user.id, expo_push_token="ExponentPushToken[local-test]", platform="ios"))
            await db.flush()
            async def deliver(key):
                live = await mobile_push.schedule(db, p, service.now_utc())
                await db.flush()
                slot = await db.scalar(select(AICompanionReminder).where(AICompanionReminder.user_id == user.id, AICompanionReminder.dedupe_key == key))
                await mobile_push.deliver(db, slot, p, service.now_utc(), live)
                await db.flush()
                return slot
            async def reply(slot, name, **kwargs):
                return await push_actions.resolve(db, user.id, p.id, slot.dedupe_key, name, **kwargs)
            water = await deliver(f"water:{day}")
            assert captured[-1]["categoryId"] == "mentor_water_later"
            assert (await reply(water, "water"))["message"] == "Записано 250 мл воды"
            assert (await reply(water, "water"))["message"] == "Записано 250 мл воды"
            assert len((await db.scalars(select(AICompanionEntry).where(AICompanionEntry.kind == "water"))).all()) == 1
            with pytest.raises(HTTPException):
                await push_actions.resolve(db, user.id, p.id + 1, water.dedupe_key, "water")

            slot = await deliver(f"train:{day}:strength")
            await reply(slot, "later", minutes=15)
            await reply(slot, "later", minutes=15)
            later = await db.scalar(select(AICompanionReminder).where(AICompanionReminder.dedupe_key == f"later:{slot.id}"))
            assert later.due_at == now + timedelta(minutes=15)
            monkeypatch.setattr(service, "now_utc", lambda: now+timedelta(minutes=15))
            await mobile_push.deliver(db, later, p, service.now_utc())
            assert captured[-1]["categoryId"] == "mentor_plan"
            assert (await reply(later, "plan"))["screen"] == "plan"
            await act(db, user, "entry", entry=EntryData(kind="wellbeing", occurred_at=now, wellbeing=4))
            daily = await db.scalar(select(AICompanionReminder).where(AICompanionReminder.dedupe_key == f"mood:{day}"))
            await mobile_push.deliver(db, daily, p, service.now_utc())
            assert daily.status == "cancelled"

            monkeypatch.setattr(service, "now_utc", lambda: now+timedelta(minutes=86))
            move = await deliver(f"move:{day}:strength")
            assert "перенесена" in (await reply(move, "move"))["message"]
            plan = WorkoutPlan.model_validate(p.data["workout_plan"])
            assert not plan.scheduled(day) and len(plan.scheduled(day+timedelta(days=1))) == 1
            assert len(plan.scheduled(day+timedelta(days=7))) == 1
    asyncio.run(run())


async def delivered_notice(db, profile, key, instant):
    """Simulate an accepted transport ticket and use the same stored action metadata as the worker."""
    live = await mobile_push.schedule(db, profile, instant)
    await db.flush()
    slot = await db.scalar(select(AICompanionReminder).where(
        AICompanionReminder.user_id == profile.user_id, AICompanionReminder.dedupe_key == key))
    notice = await mobile_push.current_notice(db, slot, profile, instant, live)
    assert notice and notice.due <= instant
    slot.context = {**slot.context, "kind": notice.kind, "offered": list(notice.actions), "delivered_ids": [1], "plan": notice.data.get("plan")}
    slot.status = "sent"
    await db.flush()


@db_only
def test_empty_rest_and_completed_program_actions(monkeypatch):
    instant = [now]
    monkeypatch.setattr(service, "now_utc", lambda: instant[0])
    async def run():
        async with database() as (db, user):
            p = await enable(db, user)
            await act(db, user, "settings", expected_version=p.version, settings=settings)
            await act(db, user, "workout_plan", expected_version=p.version,
                      workout_plan=WorkoutPlan.model_validate({**plan_data, "end_date": day.isoformat()}))
            async def reply(key, button):
                return await push_actions.resolve(db, user.id, p.id, key, button)
            workout = {"name": "Спина", "plan_day_key": "strength", "scheduled_date": day, "timer_started_at": now,
                       "exercises": [{"key": "pull", "name": "Тяга", "sets": [{}]}]}
            await act(db, user, "entry", entry=EntryData(kind="workout", occurred_at=now, workout=workout))
            records = select(AICompanionEntry).where(AICompanionEntry.kind == "workout")
            entry = await db.scalar(records)
            first = f"empty:{entry.id}:{entry.version}"
            assert (await reply(first, "restart"))["screen"] == "session"
            assert (await reply(first, "restart"))["entry_id"] == entry.id
            close = f"empty:{entry.id}:{entry.version}"
            assert (await reply(close, "close_empty"))["screen"] == "done"
            assert await db.scalar(records) is None
            await act(db, user, "entry", entry=EntryData(kind="wellbeing", occurred_at=now, energy=1))
            key = f"train:{day}:strength"
            await delivered_notice(db, p, key, now)
            short = await reply(key, "short")
            entry = await db.get(AICompanionEntry, short["entry_id"])
            assert len(entry.data["workout"]["exercises"][0]["sets"]) == 2
            w = {**entry.data["workout"], "rest_ends_at": now, "duration_seconds": 120}
            w["exercises"] = [{"key": "pull", "name": "Тяга", "sets": [{"completed": True, "reps": 8, "weight_kg": 10}]}]
            await act(db, user, "entry", resource_id=entry.id, expected_version=entry.version, entry=EntryData(kind="workout", occurred_at=now, workout=w))
            await reply(f"rest:{entry.id}:{int(now.timestamp()*1000)}", "extend")
            assert datetime.fromisoformat(entry.data["workout"]["rest_ends_at"]) == now + timedelta(seconds=30)
            with pytest.raises(HTTPException):
                await reply(f"empty:{entry.id}:{entry.version}", "close_empty")
            instant[0] += timedelta(minutes=41)
            unfinished = f"unfinished:{entry.id}"
            await delivered_notice(db, p, unfinished, instant[0])
            await reply(unfinished, "finish")
            assert entry.data["workout"]["duration_seconds"] == 120
            instant[0] += timedelta(minutes=settings.mobile.effort_delay)
            effort = f"effort:{entry.id}"
            await delivered_notice(db, p, effort, instant[0])
            await reply(effort, "right")
            assert entry.data["workout"]["effort"] == "right"
            program = next(key for key in await mobile_push.candidates(db, p, instant[0]) if key.startswith("program:"))
            await delivered_notice(db, p, program, instant[0])
            assert (await reply(program, "new_plan"))["screen"] == "new_plan"
            await reply(program, "repeat_plan")
            assert date.fromisoformat(p.data["workout_plan"]["start_date"]) == day + timedelta(days=7)
    asyncio.run(run())


@db_only
def test_single_rating_evening_stress_and_next_morning_sleep(monkeypatch):
    instant = [now]
    monkeypatch.setattr(service, "now_utc", lambda: instant[0])
    async def run():
        async with database() as (db, user):
            p = await enable(db, user)
            await act(db, user, "settings", expected_version=p.version, settings=settings)
            async def reply(key, button, **kwargs):
                return await push_actions.resolve(db, user.id, p.id, key, button, **kwargs)
            key = f"mood:{day}"
            await delivered_notice(db, p, key, now)
            assert (await reply(key, "checkin"))["screen"] == "rating"
            receipt = await reply(key, "checkin", score=4)
            entry = await db.get(AICompanionEntry, receipt["wellbeing_id"])
            assert entry.data["wellbeing"] == 4
            assert await reply(key, "checkin", score=2) == receipt
            await act(db, user, "entry", resource_id=entry.id, expected_version=entry.version,
                      entry=EntryData.model_validate({**entry.data, "stress": 5, "sleep_hours": 5}))
            instant[0] = clock(settings.mobile.stress_time)
            key = f"stress:{day}"
            await delivered_notice(db, p, key, instant[0])
            await reply(key, "calmer")
            assert entry.data["stress_change"] == "calmer"
            instant[0] = clock(settings.mobile.bedtime)
            key = f"bed:{day}"
            await delivered_notice(db, p, key, instant[0])
            await reply(key, "bed_later")
            instant[0] = now + timedelta(days=1)
            await act(db, user, "entry", entry=EntryData(kind="wellbeing", occurred_at=instant[0], energy=4))
            key = f"mood:{instant[0].date()}"
            await delivered_notice(db, p, key, instant[0])
            receipt = await reply(key, "partly")
            morning = await db.get(AICompanionEntry, receipt["wellbeing_id"])
            assert morning.data["energy"] == 4 and morning.data["sleep_quality"] == 2
            assert len((await db.scalars(select(AICompanionEntry))).all()) == 2
    asyncio.run(run())


@db_only
def test_photo_review_is_private_and_save_only_happens_once(monkeypatch, tmp_path):
    from hashlib import sha256
    from src.database.models import AIMessage
    from src.database.models.ai import attachment as attachment_model
    from test_companion_photos import photo
    monkeypatch.setattr(service, "now_utc", lambda: now)
    monkeypatch.setattr(attachment_model, "PRIVATE_MEDIA_DIR", tmp_path)
    async def run():
        async with database() as (db, user):
            p = await enable(db, user)
            await act(db, user, "settings", expected_version=p.version, settings=Settings(timezone="UTC", mobile={"topics": ["photo"]}))
            attachment = await photo(db, user)
            entry = EntryData(kind="meal", occurred_at=now, name="Обед", nutrition=targets, food_photo_attachment_ids=[attachment.id])
            req = "test-photo-estimate"
            message = await db.get(AIMessage, attachment.message_id)
            message.context_json = {"meal_estimate_request_id": req, "meal_estimate": {"entry": entry.model_dump(mode="json")}}
            await db.flush()
            await mobile_push.photo_ready(db, user.id, req, meal="lunch")
            key = "photo:" + sha256(req.encode()).hexdigest()
            await delivered_notice(db, p, key, now)
            result = await push_actions.resolve(db, user.id, p.id, key, "review")
            assert result["screen"] == "photo" and result["estimate"]["food_photo_attachment_ids"] == [attachment.id]
            assert not list(await db.scalars(select(AICompanionEntry.id)))
            for _ in range(2):
                await act(db, user, "entry", meal_estimate_request=req, entry=entry)
            assert len(list(await db.scalars(select(AICompanionEntry.id)))) == 1
            assert (await push_actions.resolve(db, user.id, p.id, key))["screen"] == "done"
    asyncio.run(run())


@db_only
def test_partial_device_delivery_does_not_repeat_accepted_push_or_answer(monkeypatch):
    from src.app.services import push_notifications as push
    monkeypatch.setattr(service, "now_utc", lambda: now)
    calls = []
    first, second = "ExponentPushToken[first-test]", "ExponentPushToken[second-test]"
    async def send(messages):
        tokens = {message["to"] for message in messages}
        calls.append(tokens)
        failed = {second} if len(calls) == 1 else set()
        return push.ExpoPushBatchResult(accepted_tokens=frozenset(tokens-failed), failed_tokens=frozenset(failed), invalid_tokens=frozenset())
    monkeypatch.setattr(push, "_send_expo_push_messages", send)
    async def run():
        async with database() as (db, user):
            p = await enable(db, user)
            await act(db, user, "settings", expected_version=p.version, settings=settings)
            db.add_all([UserPushToken(user_id=user.id, expo_push_token=token, platform="ios") for token in (first, second)])
            await db.flush()
            live = await mobile_push.schedule(db, p, now)
            await db.flush()
            row = await db.scalar(select(AICompanionReminder).where(AICompanionReminder.dedupe_key == f"water:{day}"))
            await mobile_push.deliver(db, row, p, now, live)
            assert row.status == "pending"
            await mobile_push.deliver(db, row, p, now + timedelta(minutes=2), live)
            assert row.status == "sent" and calls == [{first, second}, {second}]
            await push_actions.resolve(db, user.id, p.id, row.dedupe_key, "water")
            await mobile_push.deliver(db, row, p, now, live)
            assert row.status == "sent" and len(calls) == 2
    asyncio.run(run())


@db_only
def test_already_trained_records_reported_duration_without_fabricating_sets(monkeypatch):
    instant = now + timedelta(minutes=86)
    monkeypatch.setattr(service, "now_utc", lambda: instant)
    async def run():
        async with database() as (db, user):
            p = await enable(db, user)
            await act(db, user, "settings", expected_version=p.version, settings=settings)
            await act(db, user, "workout_plan", expected_version=p.version, workout_plan=WorkoutPlan.model_validate(plan_data))
            key = f"move:{day}:strength"
            await delivered_notice(db, p, key, instant)
            args = (db, user.id, p.id, key, "log_workout")
            preview = await push_actions.resolve(*args)
            assert preview["retrospective"] and not list(await db.scalars(select(AICompanionEntry.id)))
            result = await push_actions.resolve(*args, start_workout=True, duration_minutes=36)
            assert await push_actions.resolve(*args, start_workout=True, duration_minutes=36) == result
            entry = await db.get(AICompanionEntry, result["entry_id"])
            w = entry.data["workout"]
            assert w["duration_seconds"] == 2160 and w["timer_started_at"] is None
            assert not any(s["completed"] for e in w["exercises"] for s in e["sets"])
    asyncio.run(run())
