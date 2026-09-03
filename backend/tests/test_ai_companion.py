import asyncio
import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from src.app.services.ai.companion.domain import calculate_nutrition, convert_amount, package_count, parse_package, schedule_events
from src.app.services.ai.companion.jobs import delete_provider_resource, local_due
from src.app.services.ai.companion.schemas import EntryData, PlanData, ProfileData, Proposal, Settings
from src.app.services.ai.chat_interactive import build_ai_chat_output_schema


def plan_data(**stage):
    return PlanData.model_validate({"name": "User supplied", "timezone": "Europe/Moscow", "items": [{"name": "Example", "stages": [{"start_date": "2030-01-01", "end_date": "2030-01-03", "amount": "1", "unit": "mg", "times": ["10:00"], **stage}]}]})


@pytest.mark.parametrize("product,variant,expected", [
    ("Example", "10 мг", ("10", "mg")),
    ("Example 10 mg", "10 мг", ("10", "mg")),
    ("Example", "2,5 мг", ("2.5", "mg")),
    ("Example", "60 капсул", ("60", "capsule")),
    ("Example", "100 мкг", ("100", "mcg")),
    ("Example", "10 mg/ml", None),
    ("Blend", "5 mg + 5 mg", None),
    ("Example 5 mg", "10 mg", None),
    ("Capsules 10 mg", "", None),
    ("Example", "10 x 5 mg", None),
    ("Example", "1 флакон", None),
    ("Example", "0 mg", None),
])
def test_package_names(product, variant, expected):
    result = parse_package(product, variant)
    assert result["known"] == (expected is not None)
    if expected:
        assert (result["amount"], result["unit"]) == expected


def test_quantities_and_unit_safety():
    assert convert_amount(Decimal("250"), "mcg", "mg") == Decimal(".25")
    assert package_count(Decimal("10.1"), Decimal(0), Decimal(5)) == 3
    assert package_count(Decimal(5), Decimal(10), Decimal(5)) == 0
    with pytest.raises(ValueError):
        convert_amount(Decimal(1), "mg", "ml")
    with pytest.raises(ValueError):
        package_count(Decimal(1), Decimal(0), Decimal(0))


def test_calendar_interval_and_timezone():
    events = schedule_events(plan_data(interval_days=2))
    assert len(events) == 2
    assert events[0]["scheduled_at"] == datetime(2030, 1, 1, 7, tzinfo=timezone.utc)
    assert len({event["event_key"] for event in events}) == 2
    assert len(schedule_events(plan_data(weekdays=[1]))) == 1  # Tuesday
    with pytest.raises(ValidationError):
        plan_data(interval_days=2, weekdays=[1])
    with pytest.raises(ValidationError):
        plan_data(times=["10:00", "10:00"])
    with pytest.raises(ValidationError):
        plan_data(end_date="2029-12-31")


def test_dst_and_timezone_validation():
    from zoneinfo import ZoneInfo
    assert local_due(date(2026, 3, 8), time(2, 30), ZoneInfo("America/Chicago")) is None
    assert local_due(date(2026, 11, 1), time(1, 30), ZoneInfo("America/Chicago")).hour == 6
    plan = plan_data(start_date="2026-03-08", end_date="2026-03-08", times=["02:30"])
    plan.timezone = "America/Chicago"
    with pytest.raises(ValueError):
        schedule_events(plan)
    with pytest.raises(ValidationError):
        Settings(timezone="Mars/Nowhere")


def test_meal_weight_and_draft_validation():
    with pytest.raises(ValidationError):
        EntryData(kind="weight", occurred_at=datetime.now(), weight_kg=80)
    with pytest.raises(ValidationError):
        EntryData(kind="meal", occurred_at=datetime.now(timezone.utc), name="food")
    with pytest.raises(ValidationError):
        Proposal(kind="plan", summary="draft", profile=ProfileData())
    with pytest.raises(ValidationError):
        EntryData(kind="weight", occurred_at=datetime.now(timezone.utc), weight_kg="NaN")


def nutrition_result(weight=90, **profile):
    return calculate_nutrition(ProfileData(**{"age": 30, "sex": "male", "height_cm": 180, "activity": "low", **profile}), Decimal(str(weight)), eligibility_confirmed=True)


def test_nutrition_defaults_are_explicit_estimates():
    result = nutrition_result()
    assert result["available"] and result["rule_version"] == "balanced-adult-v1"
    assert result["nutrition"] == {"kcal": "1918", "protein": "119.9", "fat": "63.9", "carbs": "215.8"}
    assert result["maintenance_kcal"] == "2256" and result["deficit_kcal"] == "338"
    assert "не медицинское назначение" in result["note"]


def test_nutrition_requires_user_eligibility_and_complete_profile():
    assert not Settings().nutrition_auto_eligible
    assert not calculate_nutrition(ProfileData(age=30, sex="male", height_cm=180, activity="low"), Decimal(90))["available"]
    assert not calculate_nutrition(ProfileData(), Decimal(90), eligibility_confirmed=True)["available"]
    for value in (0, -10, 501, "NaN", "Infinity"):
        assert not nutrition_result(value)["available"]
    with pytest.raises(ValidationError):
        ProfileData(age=17)


@pytest.mark.parametrize("goal", ["maintain", "course"])
def test_nutrition_no_deficit_for_maintenance_or_course(goal):
    result = nutrition_result(goal=goal)
    assert result["nutrition"]["kcal"] == "2256" and result["deficit_kcal"] == "0"


def test_nutrition_deficit_cap_and_floors():
    result = nutrition_result(120, activity="high")
    assert result["available"] and Decimal(result["deficit_kcal"]) <= 500
    assert result["nutrition"]["kcal"] == "3261"
    female = nutrition_result(70, age=55, sex="female", height_cm=160)
    assert female["nutrition"]["kcal"] == "1500" and "Дефицит уменьшен" in female["note"]
    male = nutrition_result(85)
    assert Decimal(male["nutrition"]["kcal"]) >= 1800
    assert not nutrition_result(65, age=85, sex="female", height_cm=160)["available"]
    assert not nutrition_result(300, activity="high")["available"]


def test_nutrition_does_not_encourage_underweight_or_unneeded_deficit():
    assert not nutrition_result(50, goal="maintain")["available"]
    assert not nutrition_result(80)["available"]  # BMI < 25: no automatic deficit.
    assert nutrition_result(80, goal="maintain")["available"]
    assert not nutrition_result(target_weight_kg=50)["available"]
    assert not nutrition_result(target_weight_kg=90)["available"]


@pytest.mark.parametrize("raw", ['{"enabled":false}', '{"approved":false}', '{', 'null', '[]', '{"version":"incomplete"}'])
def test_nutrition_invalid_override_fails_closed(raw):
    profile = ProfileData(age=30, sex="male", height_cm=180, activity="low")
    assert not calculate_nutrition(profile, Decimal(90), raw, eligibility_confirmed=True)["available"]


def test_nutrition_versioned_override_and_macro_consistency():
    from src.app.services.ai.companion.nutrition import DEFAULT_NUTRITION_RULES
    profile = ProfileData(age=30, sex="male", height_cm=180, activity="low")
    rules = DEFAULT_NUTRITION_RULES.model_dump(mode="json")
    rules.update(version="balanced-adult-v2-test", loss_fraction="0.10")
    result = calculate_nutrition(profile, Decimal(90), json.dumps(rules), eligibility_confirmed=True)
    assert result["nutrition"]["kcal"] == "2031" and result["rule_version"] == rules["version"]
    for weight in (85, 90, 110, 140):
        n = nutrition_result(weight)["nutrition"]
        energy = Decimal(n["protein"]) * 4 + Decimal(n["fat"]) * 9 + Decimal(n["carbs"]) * 4
        assert abs(energy - Decimal(n["kcal"])) <= 1
    for patch in ({"loss_fraction": "0.50"}, {"max_deficit_kcal": 1000}, {"fat_fraction": "0.1"}, {"activity": {"low": "NaN"}}, {"kcal_floor": {"female": 500, "male": 500}}):
        assert not calculate_nutrition(profile, Decimal(90), json.dumps({**rules, **patch}), eligibility_confirmed=True)["available"]


def test_strict_schema_and_ordinary_chat_isolation():
    ordinary = build_ai_chat_output_schema()
    assert "companion_proposals" not in ordinary["properties"]
    assert "PlanData" not in ordinary["$defs"]
    schema = build_ai_chat_output_schema(include_companion=True)
    def visit(node):
        if isinstance(node, dict):
            pattern = node.get("pattern", "")
            assert not any(token in pattern for token in ("(?=", "(?!", "(?<=", "(?<!"))
            if "properties" in node:
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(schema)
    import re
    decimal_pattern = schema["$defs"]["Nutrition"]["properties"]["kcal"]["anyOf"][1]["pattern"]
    assert re.fullmatch(decimal_pattern, "1918.5")
    assert re.fullmatch(decimal_pattern, "0.000001")
    assert not re.fullmatch(decimal_pattern, "not a number")
    assert not re.fullmatch(decimal_pattern, ".")


def test_erasure_deletes_items_before_conversation_and_response():
    async def run():
        items = SimpleNamespace(list=AsyncMock(side_effect=[SimpleNamespace(data=[SimpleNamespace(id="item1")]), SimpleNamespace(data=[])]), delete=AsyncMock())
        client = SimpleNamespace(conversations=SimpleNamespace(items=items, delete=AsyncMock()), files=SimpleNamespace(delete=AsyncMock()), responses=SimpleNamespace(delete=AsyncMock()))
        await delete_provider_resource(client, "conversation", "conv1")
        items.delete.assert_awaited_once_with("item1", conversation_id="conv1")
        client.conversations.delete.assert_awaited_once_with("conv1")
        await delete_provider_resource(client, "response", "resp1")
        client.responses.delete.assert_awaited_once_with("resp1")
        with pytest.raises(ValueError):
            await delete_provider_resource(client, "local_file", "../../do-not-delete")
    asyncio.run(run())


def test_native_guard_cannot_be_bypassed_by_platform_header(monkeypatch):
    import config
    from src.app.modules.users.me import companion as module
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    verify = AsyncMock()
    monkeypatch.setattr(module, "verify_app_integrity_request", verify)
    monkeypatch.setattr(module, "ensure_app_ai_access", AsyncMock())
    async def run():
        user = SimpleNamespace(id=1)
        request = Request({"type": "http", "headers": [(b"x-app-platform", b"ios")]})
        with pytest.raises(HTTPException) as error:
            await module.native_access(request, db=None, user=user)
        assert error.value.status_code == 403
        native = Request({"type": "http", "headers": [(b"x-app-integrity-platform", b"ios")]})
        await module.native_access(native, db=None, user=user)
        assert verify.await_args.kwargs["force_enforce"] is True
    asyncio.run(run())


def test_conversation_rotation_rehydrates_once_and_tracks_response(monkeypatch):
    from src.integrations.ai.client import ProfessorClient
    from src.integrations.ai.enums import BotModel
    async def run():
        client = ProfessorClient(api_key="fake", proxy_url=None)
        create = AsyncMock(return_value="conv_new")
        monkeypatch.setattr(client, "create_conversation", create)
        response = SimpleNamespace(id="resp_test", output=[], output_text="ok", model="mock", conversation=SimpleNamespace(id="conv_new"), usage=SimpleNamespace(input_tokens=123, output_tokens=10, input_tokens_details=SimpleNamespace(cached_tokens=0)))
        requests = []
        async def fake_response(**kwargs):
            requests.append(kwargs)
            return response
        monkeypatch.setattr(client, "_create_v2_response", fake_response)
        monkeypatch.setattr(client, "_extract_v2_files", AsyncMock(return_value=[]))
        recorder = AsyncMock()
        result = await client.send_message_v2(input_text="new", conversation_id="reset:old", bot_model=BotModel.PREMIUM, user_id=1, companion_context={"profile": {"goal": "course"}}, replay_history=[{"role": "user", "content": "old"}], resource_recorder=recorder)
        assert requests[0]["input_payload"] == [{"role": "user", "content": "old"}, {"role": "user", "content": "new"}]
        assert all(tool["type"] != "code_interpreter" for tool in requests[0]["tools"])
        assert result["context_input_tokens"] == 123
        assert ("response", "resp_test") in [call.args for call in recorder.await_args_list]
        await client.close()
    asyncio.run(run())


def test_sensitive_admin_chat_requires_explicit_permission(monkeypatch):
    from src.app.modules.admin import ai_chats
    chat = SimpleNamespace(messages=[SimpleNamespace(is_sensitive=True)])
    monkeypatch.setattr(ai_chats, "get_ai_chat_by_id", AsyncMock(return_value=chat))
    async def run():
        with pytest.raises(HTTPException) as error:
            await ai_chats.get_ai_chat_detail(1, Request({"type": "http", "headers": []}), db=None, context=SimpleNamespace(has_permission=lambda _: False))
        assert error.value.status_code == 404
    asyncio.run(run())


def test_companion_tools_are_user_scoped_and_commerce_is_enforced(monkeypatch):
    from src.app.services.ai.companion import service
    from src.app.services.ai.companion.tools import CompanionToolExecutor
    monkeypatch.setattr(service, "profile_for", AsyncMock(return_value=SimpleNamespace(enabled=True, settings={})))
    read = AsyncMock(return_value=None)
    monkeypatch.setattr(service, "current_plan", read)
    async def run():
        executor = CompanionToolExecutor(None, 123)
        result = await executor.execute("get_active_plan", {"user_id": 999})
        assert result["ok"]
        read.assert_awaited_once_with(None, 123)
        assert not (await executor.execute("calculate_course_supply", {"days": 1}))["ok"]
        assert not (await executor.execute("get_entries", {"from_date": "2026-01-01", "to_date": "2027-01-01", "kind": "meal"}))["ok"]
    asyncio.run(run())
