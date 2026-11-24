import asyncio
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException
from pydantic import ValidationError
import pytest

from src.app.services.ai.companion.schemas import WorkoutPlan, WorkoutData
from src.app.services.ai.companion.workout_drafts import WorkoutDraftRequest, WorkoutDraftRead, draft_errors, workout_prompt
from src.app.services.ai.chat_interactive import build_ai_chat_output_schema
from src.app.services.ai.schemas.chat_interactive import StructuredAIChatOutput

NOW = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)


def plan():
    return {"name": "Strength", "start_date": "2026-11-23", "end_date": None, "days": [{"key": "mon", "name": "Upper", "weekdays": [0], "duration_minutes": 45, "exercises": [{"key": "bench", "name": "Bench press", "sets": 3, "target_reps": 8, "target_reps_max": 12, "target_weight_kg": None, "rest_seconds": 90}]}]}


def request():
    return WorkoutDraftRequest(mode="generate", start_date=NOW.date(), setup={"goal": "muscle", "experience": "beginner", "place": "gym", "equipment": ["dumbbells"], "weekdays": [0], "minutes": 45})


def test_workout_schema_validates_ranges_and_preserves_legacy_plans_and_sessions():
    p = plan()
    assert WorkoutPlan.model_validate(p).days[0].exercises[0].target_reps_max == 12
    p["days"][0]["exercises"][0]["target_reps_max"] = 7
    with pytest.raises(ValidationError):
        WorkoutPlan.model_validate(p)
    legacy = {"name": "Old session", "exercises": [{"key": "squat", "name": "Squat", "sets": [{"weight_kg": 0, "reps": 8, "completed": True}]}]}
    assert WorkoutData.model_validate(legacy).timer_started_at is None
    assert WorkoutData.model_validate(legacy).paused_at is None
    paused = WorkoutData.model_validate({**legacy, "paused_at": NOW, "duration_seconds": 600})
    assert WorkoutData.model_validate_json(paused.model_dump_json()).paused_at == NOW
    completed = WorkoutData.model_validate({**paused.model_dump(), "status": "completed", "rest_ends_at": NOW})
    assert completed.paused_at is None and completed.rest_ends_at is None
    for field in ["timer_started_at", "rest_ends_at", "paused_at"]:
        with pytest.raises(ValidationError):
            WorkoutData.model_validate({**legacy, field: "2026-11-23T12:00:00"})
    with pytest.raises(ValidationError):
        WorkoutDraftRequest(mode="generate", start_date=NOW.date())
    with pytest.raises(ValidationError):
        WorkoutDraftRequest(mode="revise", text="Move Monday", start_date=NOW.date())
    with pytest.raises(ValidationError):
        WorkoutDraftRead(message="Not enough information")


def test_only_dedicated_form_exposes_drafts_and_generation_respects_exact_selected_weekdays():
    assert "workout_draft" not in build_ai_chat_output_schema(include_companion=True, dialogue=True)["properties"]
    schema = build_ai_chat_output_schema(include_companion=True, dialogue=True, workout_draft=True)
    assert "workout_draft" in schema["properties"]
    p = plan()
    out = StructuredAIChatOutput(assistant_text="Ready", workout_draft=WorkoutDraftRead(plan=p, message="Ready"))
    assert draft_errors(out, request()) == []
    out.workout_draft.plan.days[0].weekdays = [0, 2]
    assert draft_errors(out, request())
    out.workout_draft = WorkoutDraftRead(message="Need details", questions=["Which days?"])
    assert draft_errors(out, request()) == []
    assert "Photos are optional" in workout_prompt(request())


@pytest.mark.parametrize("needs_retry", [False, True])
def test_draft_pipeline_is_read_only_accounts_usage_and_retries_invalid_selected_days(monkeypatch, needs_retry):
    from src.app.services.ai import chat
    from src.app.services.ai.companion import dialogue, service
    from src.integrations.ai.enums import BotModel
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    query = MagicMock(); query.scalar_one_or_none.return_value = None; query.scalar_one.return_value = "conv_workout"; query.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=query)
    profile = SimpleNamespace(id=3, enabled=True)
    saved_chat = SimpleNamespace(id=8, conversation_id="conv_workout", current_tokens=0, total_tokens=0)
    messages = []

    async def create_message(_db, payload, **kwargs):
        row = SimpleNamespace(id=100 + len(messages), created_at=NOW, context_json=payload.context_json, text=payload.text)
        messages.append(row); return row

    monkeypatch.setattr(chat, "require_ai_data_consent", AsyncMock())
    monkeypatch.setattr(chat, "get_or_create_user_chat", AsyncMock(return_value=saved_chat))
    monkeypatch.setattr(chat, "resolve_user_bot_model", AsyncMock(return_value=BotModel.FREE))
    monkeypatch.setattr(chat, "create_ai_message", create_message)
    usage = AsyncMock(); monkeypatch.setattr(chat, "create_ai_message_usage", usage)
    for name in ["update_ai_message", "update_ai_chat", "send_ai_reply_notification"]:
        monkeypatch.setattr(chat, name, AsyncMock())
    monkeypatch.setattr(chat, "get_ai_chat_by_id", AsyncMock(return_value=saved_chat))
    monkeypatch.setattr(service, "assert_session_active", AsyncMock(return_value=profile))
    monkeypatch.setattr(service, "context_for", AsyncMock(return_value={"profile": {}, "profile_version": 1, "dialogue": {"focus": "old record"}}))
    monkeypatch.setattr(dialogue, "workflow", AsyncMock(return_value=SimpleNamespace(version=2)))
    monkeypatch.setattr(dialogue, "snapshot", AsyncMock(return_value={"focus": "old record"}))
    monkeypatch.setattr(dialogue, "guard_for", AsyncMock(return_value=None))
    attach = AsyncMock(); monkeypatch.setattr(dialogue, "attach_turn", attach)
    direct = AsyncMock(); monkeypatch.setattr(dialogue, "direct_reply", direct)
    good = {"text": "Ready", "structured_output": {"assistant_text": "Ready", "workout_draft": {"plan": plan(), "message": "Review your week", "questions": []}}, "conversation_id": "conv_workout", "context_input_tokens": 20, "input_tokens": 20, "output_tokens": 10, "openai_model": "mock"}
    bad = {**good, "structured_output": {"assistant_text": "Ready", "workout_draft": {"plan": plan(), "message": "Ready", "questions": []}}}
    bad["structured_output"]["workout_draft"]["plan"]["days"][0]["weekdays"] = [2]
    provider = SimpleNamespace(send_message_v2=AsyncMock(side_effect=[bad, good] if needs_retry else [good]))
    result = asyncio.run(chat.send_user_chat_message(db, user=SimpleNamespace(id=7), text="Create plan", attachments=None, professor_client=provider, allow_commerce=False, companion_profile=profile, client_request_id="workout-request-1", dialogue_protocol=2, workout_request=request()))
    assert result.workout_draft["plan"]["days"][0]["weekdays"] == [0]
    assert result.workout_draft["message"] == "Review your week"
    assert result.meal_estimate is None and not result.basket_updated
    assert messages[1].context_json["workout_draft"] == result.workout_draft
    attach.assert_not_awaited(); direct.assert_not_awaited(); chat.send_ai_reply_notification.assert_not_awaited()
    assert usage.await_count == 1
    assert usage.call_args.args[1].input_tokens == (40 if needs_retry else 20)
    assert provider.send_message_v2.await_count == (2 if needs_retry else 1)
    args = provider.send_message_v2.call_args_list[0].kwargs
    assert args["function_tools"] == [] and "dialogue" not in args["companion_context"]
    assert "workout_draft" in args["output_schema"]["properties"]
    assert args["companion_context"]["workout_form"] == {"language": "ru"}


def test_completed_draft_retry_returns_cached_preview_without_provider_or_second_charge(monkeypatch):
    from src.app.services.ai import chat
    from src.app.services.ai.companion import workout_drafts
    payload = request()
    fingerprint = hashlib.sha256(("workout_draft:" + payload.model_dump_json() + ":" + hashlib.sha256(b"Create plan\n").hexdigest()).encode()).hexdigest()
    duplicate = SimpleNamespace(chat_id=8, text="Create plan", context_json={"generation_status": "completed", "input_fingerprint": fingerprint})
    query = MagicMock(); query.scalar_one_or_none.return_value = duplicate
    db = SimpleNamespace(execute=AsyncMock(return_value=query))
    saved = SimpleNamespace(id=8, conversation_id="conv_workout")
    cached = {"plan": plan(), "message": "Ready", "questions": []}
    monkeypatch.setattr(workout_drafts, "cached_workout_draft", AsyncMock(return_value=cached))
    monkeypatch.setattr(chat, "require_ai_data_consent", AsyncMock())
    monkeypatch.setattr(chat, "get_or_create_user_chat", AsyncMock(return_value=saved))
    monkeypatch.setattr(chat, "get_ai_chat_by_id", AsyncMock(return_value=saved))
    provider = SimpleNamespace(send_message_v2=AsyncMock())
    result = asyncio.run(chat.send_user_chat_message(db, user=SimpleNamespace(id=7), text="Create plan", attachments=None, professor_client=provider, allow_commerce=False, companion_profile=SimpleNamespace(id=3), client_request_id="workout-request-1", dialogue_protocol=2, workout_request=payload))
    assert result.workout_draft == cached
    provider.send_message_v2.assert_not_awaited()


def test_native_draft_route_uses_private_message_pipeline_and_rejects_non_images(monkeypatch):
    from src.app.modules.users.me import companion
    respond = AsyncMock(return_value={"plan": plan(), "message": "Ready", "questions": []})
    monkeypatch.setattr(companion, "_message", respond)
    photo = SimpleNamespace(content_type="image/jpeg")
    asyncio.run(companion.workout_draft(object(), request().model_dump_json(), "workout-request-1", [photo], object(), object()))
    assert respond.call_args.args[3] == [photo] and respond.call_args.args[4] == 2
    assert respond.call_args.kwargs["workout_request"] == request()
    for photos in [[photo] * 4, [SimpleNamespace(content_type="application/pdf")]]:
        with pytest.raises(HTTPException) as error:
            asyncio.run(companion.workout_draft(object(), request().model_dump_json(), "workout-request-2", photos, object(), object()))
        assert error.value.status_code == 422
    assert respond.await_count == 1


def test_saved_snapshots_and_library_preserve_old_running_sessions_and_user_isolation(monkeypatch):
    from datetime import date, timedelta
    from src.app.services.ai.companion import service
    from src.app.services.ai.companion.schemas import EntryData, Settings
    from src.app.modules.users.me.companion import workout_library
    from src.database.models import User
    from test_ai_companion_db import URL, act, database, enable
    if not URL:
        pytest.skip("Needs isolated companion_test DB")
    monkeypatch.setattr(service, "now_utc", lambda: NOW)

    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            await act(db, user, "settings", expected_version=profile.version, settings=Settings(timezone="UTC"))
            p = plan(); p["start_date"] = "2026-07-13"
            await act(db, user, "workout_plan", expected_version=profile.version, workout_plan=WorkoutPlan.model_validate(p))
            old_time = NOW - timedelta(days=133)
            snapshot = WorkoutData(name="Old upper", plan_day_key="mon", scheduled_date=old_time.date(), timer_started_at=old_time,
                exercises=[{"key": "bench", "name": "Bench press", "target_sets": 3, "target_reps": 8, "target_reps_max": 12, "rest_seconds": 90, "sets": [{"completed": False}]}])
            await act(db, user, "entry", entry=EntryData(kind="workout", occurred_at=old_time, workout=snapshot))
            p["days"][0]["exercises"][0]["target_reps"] = 15; p["days"][0]["exercises"][0]["target_reps_max"] = 20
            await act(db, user, "workout_plan", expected_version=profile.version, workout_plan=WorkoutPlan.model_validate(p))
            other = User(name="Other", surname="Training", password_hash="test-only"); db.add(other); await db.flush()
            await enable(db, other)
            await act(db, other, "entry", entry=EntryData(kind="workout", occurred_at=NOW, workout=WorkoutData(name="Private other workout", exercises=[{"key": "other", "name": "Other exercise", "sets": [{"completed": False}]}])))
            from src.database.models import AIChat, AIMessage
            from src.integrations.ai.enums import MessageSender
            from src.app.services.ai.companion.workout_drafts import cached_workout_draft
            chat = AIChat(user_id=user.id, scope="mentor", conversation_id="training-draft-cache-db")
            db.add(chat); await db.flush()
            cached = {"plan": plan(), "message": "Ready", "questions": []}
            db.add(AIMessage(user_id=user.id, chat_id=chat.id, text="Ready", sender=MessageSender.AI, context_json={"workout_draft_request_id": "workout-cache-1", "workout_draft": cached}, is_sensitive=True))
            await db.flush()
            assert await cached_workout_draft(db, user.id, "workout-cache-1") == cached
            assert await cached_workout_draft(db, other.id, "workout-cache-1") is None
            result = await workout_library(date(2026, 11, 23), date(2026, 11, 30), user, db)
            assert len(result["entries"]) == 1
            record = result["entries"][0]
            assert record["data"]["workout"]["name"] == "Old upper"
            assert record["data"]["workout"]["exercises"][0]["target_reps"] == 8
            from src.app.services.ai.companion.schemas import Action
            snapshot.paused_at = old_time + timedelta(seconds=60)
            snapshot.duration_seconds = 60
            pause_action = Action(kind="entry", request_key="workout-pause-retry", resource_id=record["id"], expected_version=record["version"], entry=EntryData(kind="workout", occurred_at=old_time, workout=snapshot))
            first_pause = await service.apply_action(db, user.id, pause_action); await db.commit()
            assert await service.apply_action(db, user.id, pause_action) == first_pause
            paused_record = (await workout_library(date(2026, 11, 23), date(2026, 11, 30), user, db))["entries"][0]
            assert paused_record["version"] == record["version"] + 1
            assert datetime.fromisoformat(paused_record["data"]["workout"]["paused_at"]) == snapshot.paused_at
            assert paused_record["data"]["workout"]["status"] == "in_progress"
            snapshot.paused_at = None
            snapshot.timer_started_at = NOW - timedelta(seconds=60)
            await act(db, user, "entry", resource_id=record["id"], expected_version=paused_record["version"], entry=EntryData(kind="workout", occurred_at=old_time, workout=snapshot))
            record = (await workout_library(date(2026, 11, 23), date(2026, 11, 30), user, db))["entries"][0]
            assert record["data"]["workout"]["paused_at"] is None
            snapshot.status = "completed"; snapshot.duration_seconds = 120
            snapshot.exercises[0].sets[0].weight_kg = Decimal(0); snapshot.exercises[0].sets[0].reps = 8; snapshot.exercises[0].sets[0].completed = True
            await act(db, user, "entry", resource_id=record["id"], expected_version=record["version"], entry=EntryData(kind="workout", occurred_at=old_time, workout=snapshot))
            saved = (await workout_library(date(2026, 11, 23), date(2026, 11, 30), user, db))["entries"][0]
            assert saved["version"] == record["version"] + 1 and saved["data"]["workout"]["status"] == "completed"
            assert (await service.profile_for(db, user.id)).data["workout_plan"]["days"][0]["exercises"][0]["target_reps"] == 15
    asyncio.run(run())


def test_dedicated_provider_instructions_apply_only_to_workout_forms_and_honor_language():
    from src.integrations.ai.client import ProfessorClient
    from src.integrations.ai.enums import BotModel
    create = AsyncMock(return_value=object())
    client = SimpleNamespace(_resolve_model_name=ProfessorClient._resolve_model_name, _load_instructions=ProfessorClient._load_instructions,
        _build_reasoning_payload=ProfessorClient._build_reasoning_payload, responses=SimpleNamespace(create=create))
    for context in [{"channel": "app"}, {"channel": "app", "workout_form": {"language": "en"}}]:
        asyncio.run(ProfessorClient._create_v2_response(client, model=BotModel.FREE, conversation_id="conv_workout", input_payload="Create plan", tools=[], companion_context=context))
        instructions = create.call_args.kwargs["instructions"]
        assert ("Возвращай только редактируемый черновик workout_draft" in instructions) == ("workout_form" in context)
        if "workout_form" in context:
            assert "en — английский" in instructions and '"language": "en"' in instructions
