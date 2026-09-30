import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from src.app.modules.telegram_ai import mentor as m, reminders as r

NOW = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)
UID = 88000000993


def test_nutrition_uses_shared_rules_and_requires_explicit_eligibility(monkeypatch):
    profile = dict(goal="weight_loss", age=35, sex="male", height_cm=180, current_weight_kg=100,
                   target_weight_kg=85, activity="moderate")
    monkeypatch.setattr(m, "snapshot", AsyncMock(return_value={"profile": profile}))
    result = asyncio.run(m.nutrition_preview(m.NutritionPreview(telegram_user_id=UID), None))
    assert not result["available"]
    result = asyncio.run(m.nutrition_preview(m.NutritionPreview(telegram_user_id=UID, eligibility_confirmed=True), None))
    assert result["available"] and float(result["nutrition"]["kcal"]) >= 1800
    profile["age"] = 16
    assert not asyncio.run(m.nutrition_preview(m.NutritionPreview(telegram_user_id=UID, eligibility_confirmed=True), None))["available"]
    profile.pop("sex")
    assert "sex" in asyncio.run(m.nutrition_preview(m.NutritionPreview(telegram_user_id=UID), None))["missing"]


def test_notification_time_does_not_change_dose_or_intake_instant():
    event = SimpleNamespace(occurred_at=NOW)
    course = SimpleNamespace(data={"timezone": "Europe/Moscow", "reminder_time": "20:00", "dose_text": "unchanged"})
    assert r.course_notification_time(event, course) == NOW.replace(hour=17)
    assert event.occurred_at == NOW and course.data["dose_text"] == "unchanged"
    course.data["reminder_time"] = None
    assert r.course_notification_time(event, course) == NOW


def test_invalid_reminder_clock_rejected():
    for clock in ["25:00", "9:00", "09:00:30", "09:00+01:00"]:
        with pytest.raises(ValidationError):
            m.CourseReminder(telegram_user_id=UID, entry_id=1, reminder_time=clock)


def test_period_average_ignores_missing_days_and_uses_saved_targets():
    def row(i, day, kind, status="confirmed", **data):
        return SimpleNamespace(id=i, kind=kind, status=status, data=data, occurred_at=NOW-timedelta(days=day))
    rows=[row(1, 10, "target", protein=100, source="user"), row(2, 2, "meal", kcal=600, protein=30),
          row(3, 2, "meal", kcal=400, protein=20), row(4, 1, "meal", kcal=2000, protein=150)]
    report=m.summarize(rows, NOW, ZoneInfo("UTC"))
    assert report["average_kcal"] == 1500 and report["nutrition_days"] == 2
    assert report["protein_target_percent"] == 100 and report["protein_target_days"] == 2


def test_owned_course_reminder_update_and_stale_lease_in_real_database(monkeypatch):
    from test_ai_companion_db import database, URL
    if not URL: pytest.skip("Isolated database required")
    monkeypatch.setattr(m, "now", lambda: NOW)
    monkeypatch.setattr(r, "now", lambda: NOW)
    async def run():
        async with database() as (db, user):
            draft=await m.record_draft(m.RecordDraft(telegram_user_id=UID, request_key="course-clock-test", kind="course", data={
                "name":"Course", "dose_text":"do not change", "source":"user", "timezone":"UTC",
                "start_date":"2030-01-01", "end_date":"2030-01-08", "weekdays":[1], "times":["20:00"]}), db)
            entry_id=draft["entry"]["id"]
            await m.record_action(m.RecordAction(telegram_user_id=UID, entry_id=entry_id, action="confirm"), db)
            with pytest.raises(HTTPException) as error:
                await m.course_reminder(m.CourseReminder(telegram_user_id=UID+1, entry_id=entry_id, reminder_time="18:00"), db)
            assert error.value.status_code == 404
            await r.options(r.Options(telegram_user_id=UID, timezone="UTC", course=True), db)
            updated=await m.course_reminder(m.CourseReminder(telegram_user_id=UID, entry_id=entry_id, reminder_time="12:00"), db)
            assert updated["entry"]["times"] == ["20:00"] and updated["entry"]["dose_text"] == "do not change"
            item=(await r.claim_due(db))["items"][0]
            receipt=r.Ack(telegram_user_id=UID, delivery_id=item["delivery_id"], token=item["token"], outcome="sent")
            assert (await r.check(receipt, db))["deliver"]
            await m.course_reminder(m.CourseReminder(telegram_user_id=UID, entry_id=entry_id, reminder_time="18:00"), db)
            assert not (await r.check(receipt, db))["deliver"]
            assert (await r.claim_due(db))["items"] == []
            await m.course_reminder(m.CourseReminder(telegram_user_id=UID, entry_id=entry_id, reminder_time="12:00"), db)
            item=(await r.claim_due(db))["items"][0]
            await r.ack(r.Ack(telegram_user_id=UID, delivery_id=item["delivery_id"], token=item["token"], outcome="sent"), db)
            await m.course_reminder(m.CourseReminder(telegram_user_id=UID, entry_id=entry_id, reminder_time="18:00"), db)
            monkeypatch.setattr(r, "now", lambda: NOW.replace(hour=18))
            assert (await r.claim_due(db))["items"] == []
    asyncio.run(run())


def test_dashboard_report_retains_replaced_targets_in_real_database(monkeypatch):
    from test_ai_companion_db import database, URL
    from src.database.models import TelegramAIJournal
    if not URL: pytest.skip("Isolated database required")
    monkeypatch.setattr(m, "now", lambda: NOW)
    async def run():
        async with database() as (db, user):
            for key, day, kind, status, data in [
                ("old", 10, "target", "replaced", {"source":"user", "protein":100, "kcal":2000}),
                ("new", 1, "target", "confirmed", {"source":"user", "protein":150, "kcal":2200}),
                ("food-old", 2, "meal", "confirmed", {"protein":100, "kcal":2000}),
                ("food-new", 0, "meal", "confirmed", {"protein":150, "kcal":2200}),
            ]:
                db.add(TelegramAIJournal(telegram_user_id=UID, request_key=key, kind=kind, status=status,
                    data=data, occurred_at=NOW-timedelta(days=day)))
            await db.flush()
            result=await m.workspace_state(db, UID)
            assert result["target"]["protein"] == 150
            assert result["weekly"]["protein_target_percent"] == 100
            report=await m.report(m.Report(telegram_user_id=UID), db)
            assert report["protein_target_percent"] == result["weekly"]["protein_target_percent"]
            assert (await m.workspace_state(db, UID+1))["target"] is None
    asyncio.run(run())
