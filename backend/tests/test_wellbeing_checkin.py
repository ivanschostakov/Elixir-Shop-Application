from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.app.services.ai.companion.schemas import Action, EntryData


def test_complete_wellbeing_checkin_round_trips_through_the_existing_action():
    payload = {
        "kind": "entry", "request_key": "wellbeing-checkin-001",
        "resource_id": 42, "expected_version": 3,
        "entry": {"kind": "wellbeing", "occurred_at": "2026-11-21T18:30:00+03:00",
                  "wellbeing": 4, "energy": 4, "mood": 2, "stress": 2,
                  "sleep_hours": "7.5", "sleep_quality": 3, "appetite": 3, "note": "A walk helped."},
    }
    action = Action.model_validate(payload)
    saved = action.entry.model_dump(mode="json")
    reread = EntryData.model_validate(saved)
    assert (reread.mood, reread.stress, reread.sleep_quality) == (2, 2, 3)
    assert reread.sleep_hours == Decimal("7.5")
    assert reread.occurred_at == datetime(2026, 11, 21, 15, 30, tzinfo=timezone.utc)
    assert action.resource_id == 42 and action.expected_version == 3


@pytest.mark.parametrize("field,value", [("mood", 0), ("mood", 4), ("stress", 0), ("stress", 6), ("sleep_quality", 0), ("sleep_quality", 4), ("sleep_hours", -1), ("sleep_hours", 24.1)])
def test_wellbeing_scores_and_sleep_have_bounded_values(field, value):
    with pytest.raises(ValidationError):
        EntryData(kind="wellbeing", occurred_at=datetime.now(timezone.utc), **{field: value})


@pytest.mark.parametrize("field", ["mood", "stress", "sleep_quality"])
def test_new_answers_are_optional_for_old_records_and_cannot_be_attached_to_weight(field):
    legacy = EntryData(kind="wellbeing", occurred_at=datetime.now(timezone.utc), wellbeing=4)
    assert getattr(legacy, field) is None
    assert getattr(EntryData(kind="wellbeing", occurred_at=legacy.occurred_at, **{field: 2}), field) == 2
    with pytest.raises(ValidationError, match="belong to a wellbeing record"):
        EntryData(kind="weight", occurred_at=legacy.occurred_at, weight_kg=70, **{field: 2})
