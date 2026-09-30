import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

import config
from src.app.services.ai.companion import service
from src.app.services.ai.companion.mentor import MentorDashboard, NutritionTotals, progress_totals
from src.app.services.ai.companion.nutrition import calculate_nutrition, DEFAULT_NUTRITION_RULES
from src.app.services.ai.companion.schemas import Action, EntryData, MeasurementData, Nutrition, PlanData, ProfileData, Proposal, Settings, WorkoutData, WorkoutPlan
from src.database.models import AIChat, AIMessage, User
from src.database.models.ai.companion import AICompanionEntry, AICompanionPlan
from test_ai_companion_db import URL, act, database, enable

db_test = pytest.mark.skipif(not URL, reason="Needs isolated companion_test DB")
NOW = datetime(2030, 1, 7, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    monkeypatch.setattr(config, "AI_COMPANION_DIALOGUE_ENABLED", True)
    monkeypatch.setattr(service, "now_utc", lambda: NOW)


def workout_plan():
    return WorkoutPlan.model_validate({"name": "Week", "start_date": NOW.date(), "days": [{
        "key": "strength", "name": "Strength", "weekdays": [NOW.weekday()],
        "exercises": [{"key": "squat", "name": "Squat", "sets": 2, "target_reps": 10, "target_weight_kg": 50}],
    }]})


def workout(**changes):
    return WorkoutData.model_validate({"name": "Strength", "plan_day_key": "strength", "scheduled_date": NOW.date(),
        "duration_seconds": 120, "exercises": [
            {"key": "squat", "name": "Squat", "sets": [{"weight_kg": 40, "reps": 2, "completed": True}, {"weight_kg": 50, "reps": 10}]},
            {"key": "press", "name": "Press", "sets": [{"weight_kg": 0, "reps": 12}]},
        ], **changes})


def entry_row(kind, at=NOW, id=1, **data):
    entry = EntryData(kind=kind, occurred_at=at, **data)
    return SimpleNamespace(id=id, kind=kind, occurred_at=at, data=entry.model_dump(mode="json"))


def test_actual_sets_only_and_independent_measurement_deltas():
    entries = [entry_row("workout", workout=workout()),
        entry_row("measurement", at=NOW - timedelta(days=1), measurement=MeasurementData(waist_cm=90, chest_cm=100)),
        entry_row("measurement", id=2, measurement=MeasurementData(waist_cm=89)),
        entry_row("wellbeing", wellbeing=4, energy=3), entry_row("wellbeing", id=2, note="No numeric score")]
    totals = progress_totals(entries)
    assert totals["workouts"] == {"sessions": 1, "completed": 0, "in_progress": 1, "completed_sets": 1, "reps": 2, "volume_kg": "80", "duration_seconds": 120}
    assert totals["measurements"]["change"]["waist_cm"] == "-1"
    assert totals["measurements"]["change"]["chest_cm"] is None
    assert totals["measurements"]["latest"]["chest_cm"] == "100"
    assert totals["wellbeing"] == {"entries": 2, "average_score": "4", "energy_measurements": 1, "average_energy": "3"}
    assert progress_totals([])["wellbeing"]["average_energy"] is None
    assert NutritionTotals(kcal=180000, protein=9000, fat=5400, carbs=22500).kcal == 180000
    partial = progress_totals([entry_row("workout", workout=workout(status="completed"))])["workouts"]
    assert partial["completed"] == 1 and partial["completed_sets"] == 1 and partial["volume_kg"] == "80"


def test_running_workout_survives_travel_but_cannot_change_schedule_identity():
    async def run():
        entry = EntryData(kind="workout", occurred_at=NOW, workout=workout())
        existing = entry_row("workout", workout=workout())
        profile = SimpleNamespace(settings={"timezone": "Pacific/Kiritimati"})
        await service.validate_workout_entry(None, 1, profile, entry, existing)
        entry.workout.plan_day_key = None
        entry.workout.scheduled_date = None
        with pytest.raises(HTTPException) as error:
            await service.validate_workout_entry(None, 1, profile, entry, existing)
        assert error.value.status_code == 422
    asyncio.run(run())


def test_strict_workout_and_measurement_payloads():
    from src.app.services.ai.companion.dialogue import can_save_immediately
    from src.app.services.ai.companion.dialogue_schemas import DialogueOperation
    for entry in (EntryData(kind="workout", occurred_at=NOW, workout=workout()), EntryData(kind="measurement", occurred_at=NOW, measurement=MeasurementData(waist_cm=80))):
        assert not can_save_immediately(DialogueOperation(kind="entry", summary="Record", evidence="record", certain=True, entry=entry), "record")
    for changes in ({"current_exercise_index": 3}, {"plan_day_key": None}, {"duration_seconds": -1}):
        with pytest.raises(ValidationError):
            workout(**changes)
    with pytest.raises(ValidationError):
        workout(status="completed", exercises=[{"key": "x", "name": "X", "sets": [{"completed": False}]}])
    with pytest.raises(ValidationError):
        workout(exercises=[{"key": "x", "name": "X", "sets": [{"completed": True}]}])
    with pytest.raises(ValidationError):
        MeasurementData()
    with pytest.raises(ValidationError):
        MeasurementData(waist_cm="NaN")
    with pytest.raises(ValidationError):
        EntryData(kind="measurement", occurred_at=NOW)
    with pytest.raises(ValidationError):
        EntryData(kind="weight", occurred_at=NOW, weight_kg=80, favorite=True)
    with pytest.raises(ValidationError):
        WorkoutPlan.model_validate({**workout_plan().model_dump(), "days": [workout_plan().days[0], workout_plan().days[0]]})


def test_gain_custom_and_existing_nutrition_safety():
    profile = ProfileData(goal="weight_gain", age=30, sex="male", height_cm=180, activity="low", target_weight_kg=75)
    result = calculate_nutrition(profile, Decimal(70), eligibility_confirmed=True)
    assert result["available"] and result["surplus_kcal"] == "300"
    assert Decimal(result["nutrition"]["kcal"]) > Decimal(result["maintenance_kcal"])
    assert result["rule_version"].endswith(":gain-v1")
    assert "Дефицит уменьшен" not in result["note"]
    assert not calculate_nutrition(profile, Decimal(70))["available"]
    for weight in (50, 85):
        assert not calculate_nutrition(profile, Decimal(weight), eligibility_confirmed=True)["available"]
    for updates in ({"goal": "custom"}, {"target_weight_kg": 65}, {"target_weight_kg": 85}):
        assert not calculate_nutrition(profile.model_copy(update=updates), Decimal(70), eligibility_confirmed=True)["available"]
    old_rules = DEFAULT_NUTRITION_RULES.model_dump_json(exclude={"gain_surplus_kcal"})
    assert not calculate_nutrition(profile, Decimal(70), old_rules, eligibility_confirmed=True)["available"]


@db_test
def test_durable_session_versions_idempotency_isolation_and_plan_preservation():
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            await act(db, user, "settings", expected_version=profile.version, settings=Settings(timezone="UTC"))
            await act(db, user, "workout_plan", expected_version=profile.version, workout_plan=workout_plan())
            action = Action(request_key="workout-start-once", kind="entry", entry=EntryData(kind="workout", occurred_at=NOW, workout=workout()))
            first = await service.apply_action(db, user.id, action)
            await db.commit()
            assert await service.apply_action(db, user.id, action) == first
            rows = await service.entries_for(db, user.id, NOW - timedelta(days=1), NOW + timedelta(days=1), "workout")
            assert len(rows) == 1
            row = rows[0]
            with pytest.raises(HTTPException) as error:
                await service.apply_action(db, user.id, action.model_copy(update={"request_key": "duplicate-session"}))
            assert error.value.status_code == 409
            updated = workout().model_dump(mode="json")
            updated["current_exercise_index"] = 1
            await act(db, user, "entry", resource_id=row.id, expected_version=row.version, entry=EntryData(kind="workout", occurred_at=NOW, workout=WorkoutData.model_validate(updated)))
            assert row.data["workout"]["current_exercise_index"] == 1
            with pytest.raises(HTTPException) as error:
                await act(db, user, "entry", resource_id=row.id, expected_version=1, entry=action.entry)
            assert error.value.status_code == 409
            await act(db, user, "profile", expected_version=profile.version, profile=ProfileData(goal="custom", preferences="Vegetarian"))
            assert profile.data["workout_plan"]["name"] == "Week"
            await act(db, user, "workout_plan", expected_version=profile.version, workout_plan=None)
            for exercise in updated["exercises"]:
                for item in exercise["sets"]:
                    item["completed"] = True
            updated.update(status="completed", duration_seconds=300)
            await act(db, user, "entry", resource_id=row.id, expected_version=row.version, entry=EntryData(kind="workout", occurred_at=NOW, workout=WorkoutData.model_validate(updated)))
            assert row.data["workout"]["current_exercise_index"] == 2
            summary = await service.summary_for(db, user.id, NOW - timedelta(days=7), NOW + timedelta(days=1))
            assert summary["workouts"]["completed"] == 1 and summary["workouts"]["volume_kg"] == "580"
            foreign = User(name="Other", surname="Mentor", password_hash="not-a-password")
            db.add(foreign)
            await db.flush()
            await enable(db, foreign)
            with pytest.raises(HTTPException) as error:
                await act(db, foreign, "entry", resource_id=row.id, expected_version=row.version, entry=action.entry)
            assert error.value.status_code == 404
            assert (await service.get_state(db, foreign.id))["mentor"]["week"]["summary"]["workouts"]["sessions"] == 0
            await act(db, user, "delete_entry", resource_id=row.id, expected_version=row.version)
            assert not await service.entries_for(db, user.id, NOW - timedelta(days=1), NOW + timedelta(days=1), "workout")
    asyncio.run(run())


@db_test
def test_dashboard_context_and_course_off_days_do_not_invent_actuals():
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            await act(db, user, "settings", expected_version=profile.version, settings=Settings(timezone="UTC"))
            nutrition = Nutrition(kcal=2000, protein=100, fat=60, carbs=250)
            await act(db, user, "profile", expected_version=profile.version, profile=ProfileData(preferences="Vegetarian", nutrition=nutrition))
            await act(db, user, "workout_plan", expected_version=profile.version, workout_plan=workout_plan())
            for at, weight in ((NOW - timedelta(days=60), 70), (NOW + timedelta(minutes=4), 99)):
                await act(db, user, "entry", entry=EntryData(kind="weight", occurred_at=at, weight_kg=weight))
            await act(db, user, "entry", entry=EntryData(kind="meal", occurred_at=NOW, name="Breakfast", favorite=True, nutrition=Nutrition(kcal=500, protein=20, fat=10, carbs=80)))
            await act(db, user, "entry", entry=EntryData(kind="measurement", occurred_at=NOW, measurement=MeasurementData(waist_cm=80)))
            await act(db, user, "entry", entry=EntryData(kind="wellbeing", occurred_at=NOW, wellbeing=4, energy=3))
            # Two-day course interval: today is an off day, not a pending task.
            start = (NOW - timedelta(days=1)).date()
            plan = PlanData.model_validate({"name": "Existing prescription", "timezone": "UTC", "items": [{"name": "Example", "stages": [{"start_date": start, "end_date": start + timedelta(days=4), "interval_days": 2, "amount": 1, "unit": "mg", "times": ["09:00"]}]}]})
            await act(db, user, "plan", expected_version=profile.version, plan=plan)
            state = await service.get_state(db, user.id)
            mentor = MentorDashboard.model_validate(state["mentor"])
            assert mentor.today.course.scheduled == 0
            assert mentor.today.workouts.scheduled == 1 and mentor.today.workouts.completed == 0
            assert mentor.week.summary.workouts.volume_kg == 0
            assert mentor.latest_weight.data.weight_kg == 70
            assert mentor.today.nutrition.remaining.kcal == 1500
            context = await service.context_for(db, user.id)
            assert context["latest_weight"]["data"]["weight_kg"] == "70"
            assert len(context["confirmed_food_today"]) == 1 and context["confirmed_food_today"][0]["data"]["favorite"]
            assert context["remaining_nutrition"]["protein"] == "80"
            assert context["profile"]["preferences"] == "Vegetarian"
            assert context["recent_wellbeing"][0]["data"]["wellbeing"] == 4
            assert context["recent_measurements"][0]["data"]["measurement"]["waist_cm"] == "80"
            assert context["active_plan"]["data"]["items"][0]["stages"][0]["interval_days"] == 2
            await act(db, user, "profile", expected_version=profile.version, profile=ProfileData(goal="custom"))
            assert profile.data["nutrition"]["kcal"] == "2000"
            await service.revoke_consent(db, user.id)
            await db.commit()
            assert (await service.get_state(db, user.id))["mentor"] is None
            assert not (await service.context_for(db, user.id))["profile"]
            with pytest.raises(HTTPException) as error:
                await act(db, user, "workout_plan", expected_version=profile.version, workout_plan=workout_plan())
            assert error.value.status_code == 409
    asyncio.run(run())


@db_test
def test_recommended_history_readable_but_old_v1_and_v2_cards_rejected(monkeypatch):
    from test_companion_dialogue import turn, card_action
    from src.app.services.ai.companion.dialogue_schemas import DialogueOperation
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            plan = PlanData.model_validate({"name": "Historical", "source": "ai_recommended_plan", "items": [{"name": "Example", "stages": [{"start_date": NOW.date(), "end_date": NOW.date(), "amount": 1, "unit": "mg", "times": ["10:00"]}]}]})
            history = AICompanionPlan(user_id=user.id, course_key="historic", version=1, status="completed", is_current=True, data=plan.model_dump(mode="json"))
            db.add(history)
            await db.commit()
            assert PlanData.model_validate((await service.get_state(db, user.id))["plan"]["data"]).source == "ai_recommended_plan"
            with pytest.raises(HTTPException) as error:
                await act(db, user, "plan", expected_version=profile.version, plan=plan)
            assert error.value.status_code == 422
            chat = AIChat(user_id=user.id, conversation_id="old-cards")
            db.add(chat)
            await db.flush()
            message = AIMessage(user_id=user.id, chat_id=chat.id, sender="ai", text="Old proposal")
            db.add(message)
            await db.flush()
            # Simulate cards persisted by the prior release, before the new guard.
            with monkeypatch.context() as patch:
                patch.setattr(service, "prepare_plan", AsyncMock(return_value=plan))
                await service.attach_proposals(db, user.id, message, [Proposal(kind="plan", plan=plan, summary="Old")], profile)
                await db.commit()
                old_v2 = await turn(db, user, "Old course", [DialogueOperation(kind="plan", summary="Old", evidence="Old course", plan=plan)])
            card = message.companion_cards[0]
            with pytest.raises(HTTPException) as error:
                await act(db, user, "confirm", message_id=message.id, action_id=card["id"], action_token=card["action_token"])
            assert error.value.status_code == 422
            with pytest.raises(HTTPException) as error:
                await card_action(db, user, old_v2, "dialogue_confirm")
            assert error.value.status_code == 422
            assert len(list((await db.execute(select(AICompanionPlan))).scalars())) == 1
            assert not list((await db.execute(select(AICompanionEntry))).scalars())
    asyncio.run(run())
