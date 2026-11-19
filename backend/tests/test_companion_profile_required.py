import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.app.services.ai.companion import service
from src.app.services.ai.companion.schemas import Action, OnboardingData, ProfileData
from src.database.models.ai.companion import AICompanionEntry, AICompanionOperation


COMPLETE = {"goal": "maintain", "age": 30, "sex": "male", "height_cm": 180, "activity": "low"}
ONBOARDING = {**COMPLETE, "current_weight_kg": "78.5"}


def profile_row():
    return SimpleNamespace(version=1, data={}, settings={"timezone": "America/Chicago"}, target_history=[])


@pytest.mark.parametrize("field,label", [("goal", "цель"), ("age", "возраст"), ("sex", "пол"), ("height_cm", "рост"), ("activity", "активность")])
def test_submitted_profile_requires_each_telegram_field(monkeypatch, field, label):
    async def run():
        data = {key: value for key, value in COMPLETE.items() if key != field}
        profile = profile_row()
        db = SimpleNamespace(flush=AsyncMock())
        weight = AsyncMock(return_value=object())
        monkeypatch.setattr(service, "latest_weight", weight)
        with pytest.raises(HTTPException) as error:
            await service.apply_payload(db, 1, profile, Action(request_key="required-profile", kind="profile", expected_version=1, profile=ProfileData(**data)))
        assert error.value.status_code == 422
        assert label in error.value.detail
        assert profile.data == {}
        db.flush.assert_not_awaited()
    asyncio.run(run())


@pytest.mark.parametrize("field", ["age", "sex", "height_cm", "activity"])
def test_submitted_profile_rejects_explicit_null(monkeypatch, field):
    async def run():
        profile = profile_row()
        monkeypatch.setattr(service, "latest_weight", AsyncMock(return_value=object()))
        with pytest.raises(HTTPException) as error:
            await service.apply_payload(None, 1, profile, Action(request_key="null-profile-field", kind="profile", expected_version=1,
                profile=ProfileData(**{**COMPLETE, field: None})))
        assert error.value.status_code == 422
        assert profile.data == {}
    asyncio.run(run())


def test_submitted_profile_requires_recorded_current_weight(monkeypatch):
    async def run():
        profile = profile_row()
        monkeypatch.setattr(service, "latest_weight", AsyncMock(return_value=None))
        with pytest.raises(HTTPException) as error:
            await service.apply_payload(None, 1, profile, Action(request_key="missing-current-weight", kind="profile", expected_version=1, profile=ProfileData(**COMPLETE)))
        assert error.value.status_code == 422 and "текущий вес" in error.value.detail
        assert profile.data == {}
    asyncio.run(run())


def test_complete_profile_saves_without_optional_fields_or_timezone_confirmation(monkeypatch):
    async def run():
        profile = profile_row()
        db = SimpleNamespace(flush=AsyncMock())
        weight = AsyncMock(return_value=object())
        monkeypatch.setattr(service, "latest_weight", weight)
        await service.apply_payload(db, 1, profile, Action(request_key="complete-profile", kind="profile", expected_version=1, profile=ProfileData(**COMPLETE)))
        assert profile.data["goal"] == "maintain"
        assert profile.data["target_weight_kg"] is None
        assert profile.data["preferences"] == profile.data["restrictions"] == ""
        assert profile.settings == {"timezone": "America/Chicago"}
        weight.assert_awaited_once_with(db, 1)
        db.flush.assert_awaited_once()
    asyncio.run(run())


def test_conversation_can_save_confirmed_answers_incrementally(monkeypatch):
    async def run():
        profile = profile_row()
        db = SimpleNamespace(flush=AsyncMock())
        weight = AsyncMock(return_value=None)
        monkeypatch.setattr(service, "latest_weight", weight)
        await service.apply_payload(db, 1, profile, Action(request_key="one-profile-answer", kind="profile", expected_version=1,
            profile=ProfileData(age=30)), source_message_id=42)
        assert profile.data["age"] == 30 and profile.data["height_cm"] is None
        assert "goal" not in profile.data
        weight.assert_not_awaited()
    asyncio.run(run())


def test_next_conversation_answer_preserves_collected_profile_fields(monkeypatch):
    async def run():
        profile = profile_row()
        profile.data = {"goal": "maintain", "age": 30, "preferences": "Vegetarian"}
        db = SimpleNamespace(flush=AsyncMock())
        monkeypatch.setattr(service, "latest_weight", AsyncMock(return_value=None))
        await service.apply_payload(db, 1, profile, Action(request_key="next-profile-answer", kind="profile", expected_version=1,
            profile=ProfileData(height_cm=180)), source_message_id=43)
        assert profile.data["goal"] == "maintain"
        assert profile.data["age"] == 30 and profile.data["height_cm"] == "180"
        assert profile.data["preferences"] == "Vegetarian"
    asyncio.run(run())


@pytest.mark.parametrize("field", list(ONBOARDING))
def test_onboarding_requires_all_six_fields_in_one_submission(field):
    with pytest.raises(ValidationError):
        OnboardingData(**{key: value for key, value in ONBOARDING.items() if key != field})


@pytest.mark.parametrize("patch", [{"age": 17}, {"age": 30.5}, {"height_cm": 49}, {"current_weight_kg": 0}, {"current_weight_kg": "NaN"}, {"activity": "unknown"}, {"goal": "custom", "custom_goal": "   "}])
def test_onboarding_rejects_invalid_answers(patch):
    with pytest.raises(ValidationError):
        OnboardingData(**{**ONBOARDING, **patch})


def test_onboarding_saves_profile_and_weight_together_preserving_optional_data(monkeypatch):
    async def run():
        profile = profile_row()
        profile.data = {"preferences": "Vegetarian", "restrictions": "Nuts", "target_weight_kg": "75"}
        db = SimpleNamespace(flush=AsyncMock(), add=MagicMock())
        monkeypatch.setattr(service, "latest_weight", AsyncMock(return_value=None))
        await service.apply_payload(db, 1, profile, Action(request_key="atomic-onboarding", kind="onboard", expected_version=1, onboarding=OnboardingData(**ONBOARDING)))
        assert profile.data["goal"] == "maintain" and profile.data["height_cm"] == "180"
        everything_optional = ("preferences", "restrictions", "target_weight_kg")
        assert [profile.data[field] for field in everything_optional] == ["Vegetarian", "Nuts", "75"]
        assert profile.settings == {"timezone": "America/Chicago"}
        entry = db.add.call_args.args[0]
        assert isinstance(entry, AICompanionEntry) and entry.user_id == 1 and entry.kind == "weight"
        assert entry.data["weight_kg"] == "78.5" and entry.source == "manual"
        db.flush.assert_awaited_once()
    asyncio.run(run())


def test_repeated_onboarding_does_not_duplicate_unchanged_weight(monkeypatch):
    async def run():
        profile = profile_row()
        db = SimpleNamespace(flush=AsyncMock(), add=MagicMock())
        monkeypatch.setattr(service, "latest_weight", AsyncMock(return_value=SimpleNamespace(data={"weight_kg": "78.50"})))
        await service.apply_payload(db, 1, profile, Action(request_key="same-weight-onboarding", kind="onboard", expected_version=1, onboarding=OnboardingData(**ONBOARDING)))
        db.add.assert_not_called()
        assert profile.data["age"] == 30
    asyncio.run(run())


def test_onboarding_retries_use_receipt_and_reenable_only_after_consent(monkeypatch):
    async def run():
        profile = profile_row()
        profile.enabled = False
        added = []
        def execute(statement):
            entity = statement.column_descriptions[0]["entity"]
            receipt = next((row for row in added if isinstance(row, AICompanionOperation)), None) if entity is AICompanionOperation else None
            return SimpleNamespace(scalar_one_or_none=lambda: receipt)
        db = SimpleNamespace(execute=AsyncMock(side_effect=execute), flush=AsyncMock(), add=added.append)
        monkeypatch.setattr(service, "profile_for", AsyncMock(return_value=profile))
        monkeypatch.setattr(service, "latest_weight", AsyncMock(return_value=None))
        consent = AsyncMock()
        monkeypatch.setattr(service, "require_consent", consent)
        action = Action(request_key="onboarding-retry-once", kind="onboard", expected_version=1, onboarding=OnboardingData(**ONBOARDING))
        first = await service.apply_action(db, 1, action)
        assert await service.apply_action(db, 1, action) == first
        assert len([row for row in added if isinstance(row, AICompanionEntry)]) == 1
        assert profile.enabled and profile.version == 2
        consent.assert_awaited_once_with(db, 1)
    asyncio.run(run())
