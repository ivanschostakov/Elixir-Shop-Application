import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException
import pytest

from src.app.services.ai.companion.food import food_estimate
from src.app.services.ai.companion.dialogue_schemas import DialogueOperation, DialogueTurn
from src.app.services.ai.companion.schemas import EntryData, ProfileData

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def meal(name="Chicken", kcal="200"):
    return DialogueOperation(kind="entry", summary="Meal", evidence=name, certain=True, resource_id=42, expected_version=8,
        entry=EntryData(kind="meal", name=name, occurred_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            nutrition={"kcal": kcal, "protein": "20", "fat": "8", "carbs": "12"}, estimated=False, assumptions="Portion estimated"))


def test_food_estimate_aggregates_ingredients_and_cannot_edit_old_records_or_other_resources():
    turn = DialogueTurn(operations=[meal(), meal("Rice", "150"), DialogueOperation(kind="profile", summary="Change profile", evidence="age", profile=ProfileData(age=60))], clear_draft=True)
    result = food_estimate(turn, NOW)
    assert result.kind == "meal" and result.name == "Chicken, Rice"
    assert result.nutrition.kcal == 350 and result.nutrition.protein == 40
    assert result.estimated is True and result.occurred_at == NOW
    assert result.assumptions == "Portion estimated"
    assert not result.favorite and not result.photo_attachment_ids
    assert food_estimate(DialogueTurn(operations=[turn.operations[-1]]), NOW) is None


@pytest.mark.parametrize("help_mode", [None, "suggest", "product"])
def test_food_estimate_pipeline_is_read_only_and_keeps_usage_accounting(monkeypatch, help_mode):
    from src.app.services.ai import chat
    from src.app.services.ai.companion import dialogue, service
    from src.integrations.ai.enums import BotModel

    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    query = MagicMock()
    query.scalar_one_or_none.return_value = None
    query.scalar_one.return_value = "conv_food"
    query.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=query)
    profile = SimpleNamespace(id=3, enabled=True)
    saved_chat = SimpleNamespace(id=8, conversation_id="conv_food", current_tokens=0, total_tokens=0)
    messages = []

    async def create_message(_db, payload, **kwargs):
        row = SimpleNamespace(id=100 + len(messages), created_at=NOW, context_json=payload.context_json, text=payload.text)
        messages.append(row)
        return row

    monkeypatch.setattr(chat, "require_ai_data_consent", AsyncMock())
    monkeypatch.setattr(chat, "get_or_create_user_chat", AsyncMock(return_value=saved_chat))
    monkeypatch.setattr(chat, "resolve_user_bot_model", AsyncMock(return_value=BotModel.FREE))
    monkeypatch.setattr(chat, "create_ai_message", create_message)
    usage = AsyncMock(); monkeypatch.setattr(chat, "create_ai_message_usage", usage)
    monkeypatch.setattr(chat, "update_ai_message", AsyncMock())
    monkeypatch.setattr(chat, "update_ai_chat", AsyncMock())
    monkeypatch.setattr(chat, "get_ai_chat_by_id", AsyncMock(return_value=saved_chat))
    notify = AsyncMock(); monkeypatch.setattr(chat, "send_ai_reply_notification", notify)
    monkeypatch.setattr(service, "assert_session_active", AsyncMock(return_value=profile))
    monkeypatch.setattr(service, "context_for", AsyncMock(return_value={"profile": {}, "profile_version": 1, "dialogue": {"focus": "old record"}}))
    monkeypatch.setattr(dialogue, "workflow", AsyncMock(return_value=SimpleNamespace(version=2)))
    monkeypatch.setattr(dialogue, "snapshot", AsyncMock(return_value={"focus": "old record"}))
    monkeypatch.setattr(dialogue, "guard_for", AsyncMock(return_value=None))
    attach = AsyncMock(); monkeypatch.setattr(dialogue, "attach_turn", attach)
    direct = AsyncMock(); monkeypatch.setattr(dialogue, "direct_reply", direct)
    response = {"text": "Food calculated", "structured_output": {"assistant_text": "Food calculated", "companion_dialogue": DialogueTurn(operations=[meal()]).model_dump(mode="json")},
        "conversation_id": "conv_food", "input_tokens": 20, "output_tokens": 10, "openai_model": "mock"}
    if help_mode == "suggest":
        from src.app.services.ai.companion import food_suggestions
        recipe = {"name": "Chicken and rice", "description": "Balanced meal", "portion": "1 bowl", "nutrition": {"kcal": 440, "protein": 30, "fat": 12, "carbs": 53}, "minutes": 25, "ingredients": ["Chicken 120 g", "Rice 60 g"], "steps": ["Cook rice", "Cook chicken and serve"], "image_query": "chicken rice"}
        response["structured_output"]["nutrition_suggestions"] = [recipe, {**recipe, "name": "Rice and chicken"}]
        monkeypatch.setattr(food_suggestions, "illustrated_suggestions", AsyncMock(return_value=[{**recipe, "image": None}]))
    provider = SimpleNamespace(send_message_v2=AsyncMock(return_value=response))
    result = asyncio.run(chat.send_user_chat_message(db, user=SimpleNamespace(id=7), text="Chicken", attachments=None, professor_client=provider,
        allow_commerce=False, companion_profile=profile, client_request_id="food-estimate-request-1", dialogue_protocol=2, meal_estimate=True, nutrition_help=help_mode))
    if help_mode:
        assert result.meal_estimate["entry"] is None
        assert result.meal_estimate["message"] == "Food calculated"
    else:
        assert result.meal_estimate["entry"]["estimated"] is True
        assert result.meal_estimate["entry"]["occurred_at"].startswith("2026-11-20")
    assert len(messages) == 2 and messages[0].text == "Chicken"
    assert messages[1].context_json["meal_estimate_request_id"] == "food-estimate-request-1"
    attach.assert_not_awaited(); direct.assert_not_awaited(); notify.assert_not_awaited()
    dialogue.workflow.assert_not_awaited()
    usage.assert_awaited_once()
    args = provider.send_message_v2.call_args.kwargs
    assert args["function_tools"] == [] and "dialogue" not in args["companion_context"]
    if help_mode == "suggest":
        assert "next_meal" in args["companion_context"]
        assert "nutrition_suggestions" in args["output_schema"]["properties"]
        assert len(result.meal_estimate["suggestions"]) == 1
        assert messages[1].context_json["meal_estimate"] == result.meal_estimate
    assert ("Не записывай" in args["input_text"] or "не записывай" in args["input_text"]) if help_mode else "не спрашивай дату" in args["input_text"]


def test_photo_only_estimation_uses_the_same_native_protected_message_path(monkeypatch):
    from src.app.modules.users.me import companion
    respond = AsyncMock(return_value={"entry": None, "message": "What is in the photo?"})
    monkeypatch.setattr(companion, "_message", respond)
    photo, request, user, db = object(), object(), object(), object()
    asyncio.run(companion.meal_estimate(request, "", "photo-estimate-1", [photo], user, db))
    args = respond.call_args
    assert args.args[3] == [photo] and args.args[4] == 2
    assert args.kwargs == {"meal_estimate": True}
    with pytest.raises(HTTPException) as error:
        asyncio.run(companion.meal_estimate(request, " ", "empty-estimate-1", None, user, db))
    assert error.value.status_code == 422 and respond.await_count == 1


@pytest.mark.parametrize("help_mode", [None, "suggest"])
def test_completed_food_retry_returns_stored_estimate_without_model_or_usage_charge(monkeypatch, help_mode):
    import hashlib
    from src.app.services.ai import chat
    from src.app.services.ai.companion import food
    prefix = "nutrition_help:suggest:" if help_mode else "meal_estimate:"
    fingerprint = hashlib.sha256((prefix + hashlib.sha256(b"Chicken\n").hexdigest()).encode()).hexdigest()
    duplicate = SimpleNamespace(chat_id=8, text="Chicken", context_json={"generation_status": "completed", "input_fingerprint": fingerprint})
    query = MagicMock(); query.scalar_one_or_none.return_value = duplicate
    db = SimpleNamespace(execute=AsyncMock(return_value=query))
    saved = SimpleNamespace(id=8, conversation_id="conv_food")
    stored = {"entry": food_estimate(DialogueTurn(operations=[meal()]), NOW).model_dump(mode="json"), "message": "Ready"}
    if help_mode:
        stored.update(entry=None, suggestions=[{"name": "Cached recipe", "image": {"url": "https://thumb.wikimedia.org/photo.jpg"}}], next_meal={"meal_type": "dinner"})
    cached = AsyncMock(return_value=stored)
    monkeypatch.setattr(food, "cached_food_estimate", cached)
    monkeypatch.setattr(chat, "get_or_create_user_chat", AsyncMock(return_value=saved))
    monkeypatch.setattr(chat, "get_ai_chat_by_id", AsyncMock(return_value=saved))
    monkeypatch.setattr(chat, "require_ai_data_consent", AsyncMock())
    model = AsyncMock(); monkeypatch.setattr(chat, "resolve_user_bot_model", model)
    provider = SimpleNamespace(send_message_v2=AsyncMock())
    result = asyncio.run(chat.send_user_chat_message(db, user=SimpleNamespace(id=7), text="Chicken", attachments=None, professor_client=provider,
        allow_commerce=False, companion_profile=SimpleNamespace(id=3), client_request_id="food-request-1", dialogue_protocol=2, meal_estimate=True, nutrition_help=help_mode))
    assert result.meal_estimate == stored
    cached.assert_awaited_once_with(db, 7, "food-request-1")
    model.assert_not_awaited(); provider.send_message_v2.assert_not_awaited()
