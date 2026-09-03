import subprocess
import sys
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from fastapi import HTTPException
from starlette.requests import Request

from src.app.services.ai.companion.schemas import PlanData, Settings
from src.app.services.ai.companion.timezones import timezone_info


@pytest.mark.parametrize("value,expected", [
    (" Europe/Moscow ", "Europe/Moscow"),
    ("мск", "Europe/Moscow"), ("Москва", "Europe/Moscow"),
    ("GMT+03:00", "Etc/GMT-3"), ("UTC+3", "Etc/GMT-3"),
    ("-0500", "Etc/GMT+5"), ("UTC+00:00", "UTC"), ("GMT", "UTC"),
    ("Europe/Kiev", "Europe/Kiev"), ("Asia/Calcutta", "Asia/Calcutta"),
    ("US/Central", "US/Central"), ("America/Chicago", "America/Chicago"),
    ("UTC+05:30", "UTC+05:30"), ("+0545", "UTC+05:45"), ("GMT-03:30", "UTC-03:30"),
])
def test_settings_and_course_share_timezone_validation(value, expected):
    assert Settings(timezone=value).timezone == expected
    plan = PlanData.model_validate({"name": "Example", "timezone": value, "items": [{"name": "Existing plan", "stages": [{"start_date": "2030-01-01", "end_date": "2030-01-02", "amount": 1, "unit": "mg", "times": ["12:00"]}]}]})
    assert plan.timezone == expected


@pytest.mark.parametrize("value", ["", "Not/AZone", "UTC+99", "UTC+14:30", "UTC+05:99", "../etc/passwd"])
def test_invalid_zone_is_not_silently_changed(value):
    with pytest.raises(ValidationError, match="часовой пояс"):
        Settings(timezone=value)


def test_fixed_offset_preserves_direction():
    east = ZoneInfo(Settings(timezone="GMT+03:00").timezone)
    west = ZoneInfo(Settings(timezone="UTC-05:00").timezone)
    assert datetime(2030, 1, 1, tzinfo=east).utcoffset() == timedelta(hours=3)
    assert datetime(2030, 7, 1, tzinfo=west).utcoffset() == timedelta(hours=-5)


def test_fractional_phone_offsets_work_for_dates_and_course_events():
    from src.app.services.ai.companion.domain import schedule_events
    for value, minutes in [("UTC+05:30", 330), ("UTC+05:45", 345), ("UTC-03:30", -210)]:
        assert datetime(2030, 7, 1, tzinfo=timezone_info(value)).utcoffset() == timedelta(minutes=minutes)
        plan = PlanData.model_validate({"name": "Example", "timezone": value, "items": [{"name": "Existing plan", "stages": [{"start_date": "2030-01-01", "end_date": "2030-01-01", "amount": 1, "unit": "mg", "times": ["12:00"]}]}]})
        assert schedule_events(plan)[0]["scheduled_at"].astimezone(timezone_info(value)).hour == 12


def test_packaged_tzdata_works_without_system_legacy_aliases():
    subprocess.run([sys.executable, "-c", "from zoneinfo import ZoneInfo, reset_tzpath; reset_tzpath(()); ZoneInfo.clear_cache(); [ZoneInfo(z) for z in ['Europe/Kiev', 'Asia/Calcutta', 'US/Central', 'Europe/Moscow']]"], check=True, capture_output=True, text=True)


def test_device_header_sync_is_after_native_verification_and_uses_only_current_user(monkeypatch):
    from src.app.modules.users.me import companion as api
    monkeypatch.setattr(api.config, "AI_COMPANION_ENABLED", True)
    verify, access, sync = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(api, "verify_app_integrity_request", verify)
    monkeypatch.setattr(api, "ensure_app_ai_access", access)
    monkeypatch.setattr(api.service, "sync_device_timezone", sync)
    db = SimpleNamespace(commit=AsyncMock())
    user = SimpleNamespace(id=42)
    def request(platform=b"ios", zone=b"Asia/Kathmandu", method="POST"):
        return Request({"type": "http", "method": method, "headers": [(b"x-app-integrity-platform", platform), (b"x-device-timezone", zone)]})
    async def run():
        with pytest.raises(HTTPException):
            await api.native_access(request(platform=b"web"), db=db, user=user)
        sync.assert_not_awaited()
        verify.side_effect = HTTPException(403, "Invalid attestation")
        with pytest.raises(HTTPException):
            await api.native_access(request(), db=db, user=user)
        sync.assert_not_awaited()
        verify.side_effect = None
        await api.native_access(request(), db=db, user=user)
        sync.assert_awaited_once_with(db, 42, "Asia/Kathmandu")
        db.commit.assert_awaited_once()
        sync.reset_mock()
        await api.native_access(request(method="DELETE"), db=db, user=user)
        sync.assert_not_awaited()
        with pytest.raises(HTTPException) as error:
            await api.native_access(request(zone=b"Not/AZone"), db=db, user=user)
        assert error.value.status_code == 422
    asyncio.run(run())


def test_local_day_bounds_follow_dst_and_fractional_phone_offsets(monkeypatch):
    from datetime import date
    from src.app.modules.users.me import companion as api
    profile = SimpleNamespace(settings={"timezone": "America/Chicago"})
    monkeypatch.setattr(api.service, "profile_for", AsyncMock(return_value=profile))
    async def run():
        start, end = await api.bounds(None, 42, date(2026, 3, 8), date(2026, 3, 9))
        assert end - start == timedelta(hours=23)
        start, end = await api.bounds(None, 42, date(2026, 11, 1), date(2026, 11, 2))
        assert end - start == timedelta(hours=25)
        profile.settings["timezone"] = "UTC+05:45"
        start, end = await api.bounds(None, 42, date(2026, 9, 3), date(2026, 9, 4))
        assert start.isoformat() == "2026-09-02T18:15:00+00:00"
        assert end - start == timedelta(days=1)
    asyncio.run(run())


def test_stale_settings_form_cannot_restore_previous_timezone(monkeypatch):
    from src.app.modules.users.me import companion as api
    from src.app.services.ai.companion.schemas import Action
    apply = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(api.service, "apply_action", apply)
    monkeypatch.setattr(api.service, "get_state", AsyncMock(return_value={}))
    async def run():
        payload = Action(kind="settings", request_key="timezone-form-test", expected_version=1, settings=Settings(timezone="Europe/Moscow", daily_time="18:00"))
        request = Request({"type": "http", "headers": [(b"x-device-timezone", b"America/Chicago")]})
        await api.action(payload, request, user=SimpleNamespace(id=42), db=SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock()))
        assert apply.await_args.args[2].settings.timezone == "America/Chicago"
        assert apply.await_args.args[2].settings.daily_time.hour == 18
    asyncio.run(run())


def test_bot_instructions_use_phone_timezone_and_never_ask_for_a_selection():
    prompt = (Path(__file__).parents[1] / "src/integrations/ai/instructions/companion.txt").read_text()
    assert "никогда не проси пользователя выбрать, назвать или подтвердить пояс" in prompt
    assert "Уточняй единицы, частоту, даты, время и часовой пояс" not in prompt
