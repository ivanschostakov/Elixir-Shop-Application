import subprocess
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from src.app.services.ai.companion.schemas import PlanData, Settings


@pytest.mark.parametrize("value,expected", [
    (" Europe/Moscow ", "Europe/Moscow"),
    ("мск", "Europe/Moscow"), ("Москва", "Europe/Moscow"),
    ("GMT+03:00", "Etc/GMT-3"), ("UTC+3", "Etc/GMT-3"),
    ("-0500", "Etc/GMT+5"), ("UTC+00:00", "UTC"), ("GMT", "UTC"),
    ("Europe/Kiev", "Europe/Kiev"), ("Asia/Calcutta", "Asia/Calcutta"),
    ("US/Central", "US/Central"), ("America/Chicago", "America/Chicago"),
])
def test_settings_and_course_share_timezone_validation(value, expected):
    assert Settings(timezone=value).timezone == expected
    plan = PlanData.model_validate({"name": "Example", "timezone": value, "items": [{"name": "Existing plan", "stages": [{"start_date": "2030-01-01", "end_date": "2030-01-02", "amount": 1, "unit": "mg", "times": ["12:00"]}]}]})
    assert plan.timezone == expected


@pytest.mark.parametrize("value", ["", "Not/AZone", "UTC+99", "UTC+05:30", "../etc/passwd"])
def test_invalid_zone_is_not_silently_changed(value):
    with pytest.raises(ValidationError, match="Выберите часовой пояс"):
        Settings(timezone=value)


def test_fixed_offset_preserves_direction():
    east = ZoneInfo(Settings(timezone="GMT+03:00").timezone)
    west = ZoneInfo(Settings(timezone="UTC-05:00").timezone)
    assert datetime(2030, 1, 1, tzinfo=east).utcoffset() == timedelta(hours=3)
    assert datetime(2030, 7, 1, tzinfo=west).utcoffset() == timedelta(hours=-5)


def test_packaged_tzdata_works_without_system_legacy_aliases():
    subprocess.run([sys.executable, "-c", "from zoneinfo import ZoneInfo, reset_tzpath; reset_tzpath(()); ZoneInfo.clear_cache(); [ZoneInfo(z) for z in ['Europe/Kiev', 'Asia/Calcutta', 'US/Central', 'Europe/Moscow']]"], check=True, capture_output=True, text=True)
