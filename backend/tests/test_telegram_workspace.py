import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.app.modules.telegram_ai import mentor as m, reminders as r, profile as p

UID = 88000000991
NOW = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)


def course(**changes):
    return m.Course.model_validate(dict(name="Existing prescription", dose_text="as prescribed", source="specialist",
        start_date="2030-01-01", end_date="2030-01-31", weekdays=[1], times=["09:00"], timezone="UTC", **changes))


def test_course_weekly_is_not_daily_and_interval_is_anchored():
    assert [d.day for d in m.course_dates(course())] == [1, 8, 15, 22, 29]
    data = course().model_dump()
    data.update(weekdays=[], interval_days=10)
    assert [d.day for d in m.course_dates(m.Course.model_validate(data))] == [1, 11, 21, 31]


@pytest.mark.parametrize("changes", [
    {"timezone": "Missing/Zone"}, {"weekdays": []}, {"weekdays": [7]}, {"interval_days": 7},
    {"times": ["25:00"]}, {"times": ["10:00", "10:00"]}, {"supply_amount": 20},
    {"end_date": "2032-01-01"}, {"source": "ai"},
])
def test_course_rejects_ambiguous_or_fabricated_schema(changes):
    values = course().model_dump()
    with pytest.raises(ValidationError):
        m.Course.model_validate({**values, **changes})


def test_no_remaining_without_explicit_target_and_unknown_macros_stay_unknown():
    assert m.remaining(None, {"kcal": 400}) is None
    assert m.remaining({"source": "ai", "kcal": 2000}, {"kcal": 400}) is None
    assert m.remaining({"source": "user", "kcal": 2000}, {"kcal": 400}) == {"kcal": 1600}
    assert m.remaining({"source": "specialist", "kcal": 1800, "protein": 120}, {"kcal": 2000, "protein": 80}) == {"kcal": 0, "protein": 40}


def test_reminder_grace_and_changed_schedule_are_explicit():
    assert r.expired({"reminder_kind": "course"}, NOW-timedelta(minutes=31), NOW)
    assert not r.expired({"reminder_kind": "course"}, NOW-timedelta(minutes=29), NOW)
    assert r.expired({"reminder_kind": "evening"}, NOW-timedelta(hours=13), NOW)
    before = {"morning": "09:00", "timezone": "UTC", "weekday": 6}
    assert r.schedule_changed(before, {**before, "morning": "10:00"}, "morning")
    assert not r.schedule_changed(before, {**before, "weekday": 1}, "morning")


def test_inactivity_sends_once_per_episode_and_reads_message_activity(monkeypatch):
    activity = NOW-timedelta(days=5)
    rule = SimpleNamespace(telegram_user_id=UID, occurred_at=activity, data={
        "next": {"inactivity": (NOW-timedelta(days=2)).isoformat()}, "inactivity_days": 3,
        "inactivity_last_episode": activity.isoformat(), "timezone": "UTC", "course": False})
    def results(rows): return SimpleNamespace(scalars=lambda: rows)
    db = SimpleNamespace(execute=AsyncMock(side_effect=[None, results([]), results([rule]),
        SimpleNamespace(scalar_one_or_none=lambda: activity), results([])]), flush=AsyncMock(), commit=AsyncMock())
    enqueue = AsyncMock()
    monkeypatch.setattr(r, "enqueue", enqueue)
    monkeypatch.setattr(r, "now", lambda: NOW)
    assert asyncio.run(r.claim_due(db)) == {"items": []}
    enqueue.assert_not_awaited()
    activity_query = db.execute.await_args_list[3].args[0]
    assert "activity" in str(activity_query.compile(compile_kwargs={"literal_binds": True}))


def test_activity_and_legacy_settings_lock_scheduler_before_user(monkeypatch):
    from src.app.modules.telegram_ai import journal
    activity = SimpleNamespace(occurred_at=NOW)
    result = SimpleNamespace(scalar_one_or_none=lambda: activity, scalars=lambda: [])
    db = SimpleNamespace(execute=AsyncMock(return_value=result), commit=AsyncMock())
    monkeypatch.setattr(r, "options_for", AsyncMock(return_value=None))
    asyncio.run(m.touch(p.Identity(telegram_user_id=UID), db))
    assert "pg_advisory_xact_lock(733000111)" in str(db.execute.await_args_list[0].args[0])
    assert db.execute.await_args_list[1].args[1] == {"id": -UID}
    db.execute.reset_mock()
    db.get = AsyncMock(return_value=SimpleNamespace(timezone="UTC", daily_time="20:00", next_at=NOW))
    asyncio.run(journal.reminder_settings(journal.ReminderUpdate(telegram_user_id=UID, timezone="UTC", daily_time="20:00"), db))
    assert "pg_advisory_xact_lock(733000111)" in str(db.execute.await_args_list[0].args[0])
    assert db.execute.await_args_list[1].args[1] == {"id": -UID}


def test_record_models_reject_invalid_data_and_nonfinite_numbers():
    for kind, data in [("target", {"kcal": float("nan")}), ("measurement", {}),
        ("wellbeing", {"score": 9}), ("program", {"exercises": []}),
        ("workout", {"sets": [], "duration_minutes": 10})]:
        with pytest.raises(ValidationError):
            m.RecordDraft(telegram_user_id=UID, request_key="valid-key", kind=kind, data=data)


@pytest.mark.parametrize("duration", [0, -1, 1441, float("nan"), float("inf")])
def test_activity_requires_a_real_bounded_duration(duration):
    with pytest.raises(ValidationError):
        m.RecordDraft(telegram_user_id=UID, request_key="activity-key", kind="activity_log",
            data={"name": "Walk", "duration_minutes": duration})


def test_activity_is_not_a_strength_workout_or_program():
    entry = m.RecordDraft(telegram_user_id=UID, request_key="activity-key", kind="activity_log",
        data={"name": "Walk", "duration_minutes": 30})
    assert entry.data == {"name": "Walk", "duration_minutes": 30}
    row = SimpleNamespace(id=1, kind=entry.kind, status="confirmed", data=entry.data, occurred_at=NOW)
    result = m.summarize([row], NOW, ZoneInfo("UTC"))
    assert result["workouts"] == result["duration_minutes"] == result["volume_kg"] == 0
    assert result["activities"] == 1 and result["activity_duration_minutes"] == 30


def test_finish_never_uses_chat_elapsed_time_as_duration(monkeypatch):
    monkeypatch.setattr(m, "lock", AsyncMock())
    entry = SimpleNamespace(id=7, kind="workout", status="active", occurred_at=NOW-timedelta(seconds=54),
        data={"sets": [{"exercise": "Squat", "weight_kg": 40, "reps": 10}]})
    monkeypatch.setattr(m, "owned", AsyncMock(return_value=entry))
    monkeypatch.setattr(m, "now", lambda: NOW)
    db = SimpleNamespace(commit=AsyncMock())
    with pytest.raises(HTTPException) as error:
        asyncio.run(m.workout_finish(m.WorkoutFinish(telegram_user_id=UID, entry_id=7), db))
    assert error.value.status_code == 422
    assert entry.status == "active" and "duration_minutes" not in entry.data
    db.commit.assert_not_awaited()
    result = asyncio.run(m.workout_finish(m.WorkoutFinish(telegram_user_id=UID, entry_id=7, duration_minutes=30), db))
    assert result["entry"]["duration_minutes"] == 30
    assert entry.status == "confirmed"


def test_weekly_stats_only_count_confirmed_real_entries():
    def row(kind, status, **data):
        return SimpleNamespace(kind=kind, status=status, data=data, occurred_at=NOW-timedelta(days=1), id=1)
    rows = [row("meal", "confirmed", kcal=500), row("meal", "draft", kcal=900),
        row("workout", "confirmed", sets=[{"weight_kg": 40, "reps": 10}, {"weight_kg": 45, "reps": 8}], duration_minutes=35),
        row("course_event", "done"), row("course_event", "pending"), row("course_event", "cancelled")]
    result = m.summarize(rows, NOW, ZoneInfo("UTC"))
    assert result["nutrition"]["kcal"] == 500
    assert result["volume_kg"] == 760 and result["duration_minutes"] == 35
    assert result["course_due"] == 2 and result["course_done"] == 1
    assert result["weight_change_kg"] is None


def test_seven_and_thirty_day_reports_have_measured_averages_not_fabricated_days():
    def row(index, days, kind, **data):
        return SimpleNamespace(id=index, occurred_at=NOW-timedelta(days=days), kind=kind, status="confirmed", data=data)
    rows = [row(1, 20, "weight", weight_kg=90), row(2, 3, "weight", weight_kg=82), row(3, 1, "weight", weight_kg=80),
        row(4, 1, "wellbeing", score=4, energy_score=3), row(5, 2, "wellbeing", score=2),
        row(6, -1, "weight", weight_kg=999)]
    weekly = m.summarize(rows, NOW, ZoneInfo("UTC"))
    monthly = m.summarize(rows, NOW, ZoneInfo("UTC"), 30)
    assert weekly["weight_change_kg"] == -2 and monthly["weight_change_kg"] == -10
    assert weekly["weight_mean_7d"] == monthly["weight_mean_7d"] == 81
    assert weekly["weight_samples_7d"] == 2 and monthly["weight_measurements"] == 3
    assert weekly["wellbeing_mean"] == 3 and weekly["energy_mean"] == 3
    assert weekly["wellbeing_samples"] == 2 and weekly["energy_samples"] == 1


def test_stopping_course_keeps_past_unmarked_events_and_disables_delivery(monkeypatch):
    monkeypatch.setattr(m, "lock", AsyncMock())
    monkeypatch.setattr(m, "now", lambda: NOW)
    course_row = SimpleNamespace(id=5, kind="course", status="confirmed", occurred_at=NOW, data={})
    future = SimpleNamespace(id=7, status="pending", data={"course_id": 5})
    monkeypatch.setattr(m, "owned", AsyncMock(return_value=course_row))
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: [future])), commit=AsyncMock())
    asyncio.run(m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=5, action="stop"), db))
    assert future.status == "cancelled" and course_row.status == "stopped"
    assert "occurred_at >=" in str(db.execute.await_args.args[0])
    pending_past = SimpleNamespace(status="pending", data={"course_id": 5})
    delivery = SimpleNamespace(telegram_user_id=UID, kind="reminder", status="leased", data={"token": "a"*32, "event_id": 8})
    db.get = AsyncMock(side_effect=[delivery, pending_past, course_row])
    result = asyncio.run(r.check(r.Ack(telegram_user_id=UID, delivery_id=10, token="a"*32, outcome="sent"), db))
    assert result == {"deliver": False}


def test_reminder_options_validate_and_weekly_has_real_weekday():
    for changes in ({"timezone": "bad/zone"}, {"morning": "99:00"}, {"inactivity_days": 0}, {"weekday": 7}):
        with pytest.raises(ValidationError):
            r.Options(telegram_user_id=UID, **changes)
    settings = dict(timezone="UTC", weekly="10:00", weekday=6)
    next_at = r.scheduled(settings, "weekly", NOW)
    assert next_at.weekday() == 6 and next_at.hour == 10


def test_profile_fills_only_missing_verified_facts_and_preserves_null(monkeypatch):
    db = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(data={"age": None, "goal": "weight_gain"}, version=4)))
    legacy = AsyncMock(return_value={"age": 40, "current_weight_kg": 90})
    monkeypatch.setattr(p, "legacy_profile", legacy)
    result = asyncio.run(p.snapshot(db, UID))
    assert result["profile"] == {"age": None, "goal": "weight_gain", "current_weight_kg": 90}
    legacy.assert_awaited_once_with(db, UID)


def test_ack_requires_current_owned_lease_and_retry_is_not_sent(monkeypatch):
    monkeypatch.setattr(r, "now", lambda: NOW)
    row = SimpleNamespace(status="leased", data={"token": "a"*32, "attempts": 2})
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: row)), commit=AsyncMock())
    payload = r.Ack(telegram_user_id=UID, delivery_id=7, token="a"*32, outcome="retry")
    result = asyncio.run(r.ack(payload, db))
    assert "pg_advisory_xact_lock(733000111)" in str(db.execute.await_args_list[0].args[0])
    assert result["status"] == "pending"
    assert datetime.fromisoformat(row.data["retry_at"]) > NOW
    row.status = "leased"
    with pytest.raises(HTTPException) as error:
        asyncio.run(r.ack(payload.model_copy(update={"token": "b"*32}), db))
    assert error.value.status_code == 409
    asyncio.run(r.ack(payload.model_copy(update={"outcome": "sent"}), db))
    assert row.status == "sent"
    asyncio.run(r.ack(payload.model_copy(update={"outcome": "sent"}), db))
    assert row.status == "sent"


def test_set_retry_is_idempotent_and_changed_payload_conflicts(monkeypatch):
    monkeypatch.setattr(m, "lock", AsyncMock())
    entry = SimpleNamespace(id=7, kind="workout", status="active", occurred_at=NOW, data={"sets": [], "set_receipts": {}})
    monkeypatch.setattr(m, "owned", AsyncMock(return_value=entry))
    db = SimpleNamespace(commit=AsyncMock())
    payload = m.SetInput(telegram_user_id=UID, request_key="set-request-1", entry_id=7,
        exercise_set={"exercise": "Squat", "weight_kg": 40, "reps": 10})
    asyncio.run(m.workout_set(payload, db))
    asyncio.run(m.workout_set(payload, db))
    assert len(entry.data["sets"]) == 1
    with pytest.raises(HTTPException) as error:
        asyncio.run(m.workout_set(payload.model_copy(update={"exercise_set": m.WorkoutSet(exercise="Squat", weight_kg=50, reps=10)}), db))
    assert error.value.status_code == 409


def test_gates_default_open_and_can_close_individual_section(monkeypatch):
    monkeypatch.delenv("TELEGRAM_MENTOR_CLOSED_SECTIONS", raising=False)
    assert all(m.section_enabled(s) for s in m.SECTIONS)
    monkeypatch.setenv("TELEGRAM_MENTOR_CLOSED_SECTIONS", "course,workouts")
    assert not m.section_enabled("course") and m.section_enabled("food")
    with pytest.raises(HTTPException):
        m.require_section("workouts")


def test_database_vertical_workflows_and_multiple_course_items():
    from test_ai_companion_db import database, URL
    if not URL:
        pytest.skip("Parent runs isolated PostgreSQL tests serially")
    async def run():
        async with database() as (db, user):
            for index in range(2):
                plan = await m.record_draft(m.RecordDraft(telegram_user_id=UID, request_key=f"course-item-{index}", kind="course", data=course().model_dump(mode="json")), db)
                await m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=plan["entry"]["id"], action="confirm"), db)
                await m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=plan["entry"]["id"], action="confirm"), db)
            state = await m.workspace_state(db, UID)
            assert len(state["courses"]) == 2
            assert all(len(c["calendar"]) == 5 for c in state["courses"])
            assert (await m.workspace_state(db, UID+1))["courses"] == []
            started = await m.workout_start(m.WorkoutStart(telegram_user_id=UID, request_key="workout-start-1"), db)
            entry_id = started["entry"]["id"]
            payload = m.SetInput(telegram_user_id=UID, entry_id=entry_id, request_key="workout-set-1", exercise_set={"exercise": "Squat", "weight_kg": 40, "reps": 10})
            await m.workout_set(payload, db)
            await m.workout_set(payload, db)
            finished = await m.workout_finish(m.WorkoutFinish(telegram_user_id=UID, entry_id=entry_id, duration_minutes=30), db)
            assert len(finished["entry"]["sets"]) == 1
            assert finished["entry"]["duration_minutes"] == 30
            assert (await m.workout_start(m.WorkoutStart(telegram_user_id=UID, request_key="workout-start-1"), db))["entry"]["id"] == entry_id
    asyncio.run(run())


def test_activity_draft_confirmation_and_ownership_in_real_database(monkeypatch):
    from test_ai_companion_db import database, URL
    if not URL:
        pytest.skip("An isolated PostgreSQL database is required")
    monkeypatch.setattr(m, "now", lambda: NOW)
    async def run():
        async with database() as (db, user):
            result = await m.record_draft(m.RecordDraft(telegram_user_id=UID, request_key="activity-original",
                kind="activity_log", data={"name": "Walk", "duration_minutes": 30}), db)
            entry_id = result["entry"]["id"]
            assert not (await m.workspace_state(db, UID))["today_activities"]
            with pytest.raises(HTTPException) as error:
                await m.record_action(m.RecordAction(telegram_user_id=UID+1, entry_id=entry_id, action="confirm"), db)
            assert error.value.status_code == 404
            await m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=entry_id, action="confirm"), db)
            await m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=entry_id, action="confirm"), db)
            state = await m.workspace_state(db, UID)
            assert len(state["today_activities"]) == 1
            assert state["today_activities"][0]["duration_minutes"] == 30
            assert not state["today_workouts"] and state["program"] is None
            assert state["weekly"]["activities"] == 1 and state["weekly"]["workouts"] == 0
            assert {"id": entry_id, "kind": "activity_log", "status": "confirmed"} in state["record_statuses"]
            report = await m.report(m.Report(telegram_user_id=UID), db)
            assert report["activities"] == 1 and report["activity_duration_minutes"] == 30
    asyncio.run(run())


def test_conversational_workout_replaces_owned_legacy_active_only_on_confirmation(monkeypatch):
    from test_ai_companion_db import database, URL
    if not URL:
        pytest.skip("An isolated PostgreSQL database is required")
    monkeypatch.setattr(m, "now", lambda: NOW)
    async def run():
        async with database() as (db, user):
            active = (await m.workout_start(m.WorkoutStart(telegram_user_id=UID, request_key="legacy-start"), db))["entry"]
            data = {"sets": [{"exercise": "Squat", "weight_kg": 40, "reps": 10}],
                "duration_minutes": 30, "active_entry_id": active["id"]}
            draft = (await m.record_draft(m.RecordDraft(telegram_user_id=UID, request_key="dialogue-finish",
                kind="workout", data=data), db))["entry"]
            assert (await m.workspace_state(db, UID))["active_workout"]["id"] == active["id"]
            await m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=draft["id"], action="confirm"), db)
            await m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=draft["id"], action="confirm"), db)
            state = await m.workspace_state(db, UID)
            assert state["active_workout"] is None and len(state["today_workouts"]) == 1
            assert state["weekly"]["workouts"] == 1 and state["weekly"]["duration_minutes"] == 30
            assert (await m.read_record(m.RecordRead(telegram_user_id=UID, entry_id=active["id"]), db))["entry"]["status"] == "replaced"
            stale = (await m.record_draft(m.RecordDraft(telegram_user_id=UID, request_key="stale-finish",
                kind="workout", data=data), db))["entry"]
            with pytest.raises(HTTPException) as error:
                await m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=stale["id"], action="confirm"), db)
            assert error.value.status_code == 409
            foreign = (await m.record_draft(m.RecordDraft(telegram_user_id=UID+1, request_key="foreign-finish",
                kind="workout", data=data), db))["entry"]
            with pytest.raises(HTTPException) as error:
                await m.record_action(m.RecordAction(telegram_user_id=UID+1, entry_id=foreign["id"], action="confirm"), db)
            assert error.value.status_code == 404
    asyncio.run(run())
