import asyncio
from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

import config
from src.app.services.ai.companion import dialogue, service
from src.app.services.ai.companion.dialogue_schemas import DialogueOperation, DialogueTurn, Intake
from src.app.services.ai.companion.dialogue_tools import execute_dialogue_tool, course_report, quick_report
from src.app.services.ai.companion.jobs import reminder_text, schedule_recurring
from src.app.services.ai.companion.schemas import Action, EntryData, Settings, PlanData
from src.app.services.ai.chat_interactive import build_ai_chat_output_schema
from src.database.models import AIMessage, User
from src.database.models.ai.companion import AICompanionDialogue, AICompanionEntry, AICompanionEvent, AICompanionReminder
from src.integrations.ai.enums import MessageSender
from test_ai_companion_db import database, enable, act, URL

db_test = pytest.mark.skipif(not URL, reason="Needs isolated companion_test DB")


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    monkeypatch.setattr(config, "AI_COMPANION_DIALOGUE_ENABLED", True)


def weight(value="84", **overrides):
    return DialogueOperation.model_validate({"kind": "entry", "summary": f"Вес {value} кг", "evidence": f"вес {value}", "certain": True,
        "entry": {"kind": "weight", "weight_kg": value, "occurred_at": datetime.now(timezone.utc).isoformat()}, **overrides})


async def turn(db, user, text, operations=(), **kwargs):
    flow = await dialogue.workflow(db, user.id, True)
    source = await dialogue.say(db, user.id, text, sender=MessageSender.USER)
    reply = await dialogue.say(db, user.id, "Проверьте результат.")
    await dialogue.attach_turn(db, user.id, reply, DialogueTurn(operations=list(operations), **kwargs), source, allow_commerce=False, expected_workflow_version=flow.version)
    await db.commit()
    return reply


async def card_action(db, user, message, kind, index=0, **kwargs):
    card = message.context_json["dialogue_cards"][index]
    return await act(db, user, kind, message_id=message.id, action_id=card["id"], action_token=card["action_token"], **kwargs)


def test_immediate_save_policy_and_strict_payloads():
    op = weight()
    assert dialogue.can_save_immediately(op, "сегодня вес 84")
    assert not dialogue.can_save_immediately(weight("42", evidence="вес 84"), "вес 84")
    for text in ("если вес 84", "например вес 84", "завтра вес 84", "не вес 84", "«вес 84»", "вес 84?", "вес 90"):
        assert not dialogue.can_save_immediately(op, text)
    with pytest.raises(ValidationError):
        DialogueOperation(kind="event", summary="event", evidence="принял", status="done")
    with pytest.raises(ValidationError):
        Intake(name="test", local_date=date.today(), amount=1)
    schema = build_ai_chat_output_schema(include_companion=True, dialogue=True)
    assert "companion_dialogue" in schema["properties"]
    assert "companion_dialogue" not in build_ai_chat_output_schema()["properties"]
    def verify(node):
        if isinstance(node, dict):
            if "properties" in node:
                assert set(node["properties"]) == set(node["required"])
                assert node["additionalProperties"] is False
            for item in node.values(): verify(item)
        elif isinstance(node, list):
            for item in node: verify(item)
    verify(schema)


def test_ai_recommended_course_is_supported_and_prompt_is_advisory():
    from pathlib import Path
    plan = PlanData.model_validate({"name": "Рекомендация", "source": "ai_recommended_plan", "items": [{"name": "Example", "stages": [{"start_date": "2030-01-01", "end_date": "2030-01-03", "amount": 1, "unit": "mg", "times": ["10:00"]}]}]})
    assert plan.source == "ai_recommended_plan"
    prompt = (Path(__file__).parents[1] / "src/integrations/ai/instructions/companion-dialogue.txt").read_text()
    assert "предложить конкретную дозировку, частоту, длительность" in prompt
    assert "source=ai_recommended_plan" in prompt
    assert "местное время по часам телефона без UTC offset и без повторов" in prompt
    assert "Никогда не пиши «подтвердите запись», если не вернул соответствующую операцию" in prompt
    assert "Не назначай препараты или дозировки" not in prompt


@db_test
def test_ai_recommended_course_has_server_disclosure():
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            plan = PlanData.model_validate({"name": "Рекомендация", "source": "ai_recommended_plan", "items": [{"name": "Example", "stages": [{"start_date": "2030-01-01", "end_date": "2030-01-03", "amount": 1, "unit": "mg", "times": ["10:00"]}]}]})
            reply = await turn(db, user, "составь курс", [DialogueOperation(kind="plan", summary="Курс Example", evidence="составь курс", plan=plan)])
            card = reply.dialogue_cards[0]
            assert card["state"] == "pending"
            assert card["summary"].startswith("Рекомендация ИИ — не медицинское назначение.")
            assert await service.current_plan(db, user.id) is None
    asyncio.run(run())


@db_test
def test_auto_save_undo_and_idempotent_action():
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            message = await turn(db, user, "вес 84", [weight()])
            card = message.dialogue_cards[0]
            assert card["state"] == "saved" and card["can_undo"]
            assert "undo" not in card and "guard" not in card
            assert profile.settings["checkin_time"] == "21:00:00"
            assert len(list((await db.execute(select(AICompanionEntry))).scalars())) == 1
            action = Action(request_key="same-undo-key", kind="dialogue_undo", message_id=message.id, action_id=card["id"], action_token=card["action_token"])
            first = await service.apply_action(db, user.id, action)
            await db.commit()
            assert await service.apply_action(db, user.id, action) == first
            assert not list((await db.execute(select(AICompanionEntry))).scalars())
    asyncio.run(run())


@db_test
def test_no_auto_save_without_consent_and_draft_survives():
    async def run():
        async with database() as (db, user):
            await service.ensure_default_profile(db, user.id)
            draft = {"kind": "course", "collected": "Название Example, курс уже начат", "missing": ["длительность", "время"]}
            message = await turn(db, user, "вес 84", [weight()], draft=draft)
            assert all(c["state"] == "pending" for c in message.dialogue_cards)
            assert not list((await db.execute(select(AICompanionEntry))).scalars())
            assert not (await dialogue.workflow(db, user.id)).draft
            await card_action(db, user, message, "dialogue_confirm", index=1, consent_version=config.AI_COMPANION_CONSENT_VERSION, adult_confirmed=True)
            assert (await dialogue.workflow(db, user.id)).draft["collected"] == draft["collected"]
            assert (await dialogue.snapshot(db, user.id))["draft"]["missing"] == draft["missing"]
    asyncio.run(run())


@db_test
def test_correction_targets_existing_record_and_stale_undo_refuses():
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            first = await turn(db, user, "вес 84", [weight()])
            row = (await db.execute(select(AICompanionEntry))).scalar_one()
            original_time = row.occurred_at
            await card_action(db, user, first, "dialogue_edit")
            correction = weight("83.4", evidence="83,4", resource_id=row.id, expected_version=row.version)
            correction.entry.occurred_at = original_time
            second = await turn(db, user, "исправь на 83,4", [correction])
            assert second.dialogue_cards[0]["state"] == "saved"
            assert row.data["weight_kg"] == "83.4" and row.occurred_at == original_time
            assert len(list((await db.execute(select(AICompanionEntry))).scalars())) == 1
            with pytest.raises(HTTPException) as stale:
                await card_action(db, user, first, "dialogue_undo")
            assert stale.value.status_code == 409
            await card_action(db, user, second, "dialogue_undo")
            assert row.data["weight_kg"] == "84"
    asyncio.run(run())


@db_test
def test_edit_cannot_silently_create_another_record():
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            first = await turn(db, user, "вес 84", [weight()])
            await card_action(db, user, first, "dialogue_edit")
            bad = await turn(db, user, "вес 83", [weight("83")])
            assert bad.dialogue_cards[0]["state"] == "needs_correction"
            assert len(list((await db.execute(select(AICompanionEntry))).scalars())) == 1
    asyncio.run(run())


@db_test
def test_date_only_intake_is_not_fabricated_current_time_and_is_searchable():
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            yesterday = (service.now_utc().astimezone(dialogue.timezone_info(profile.settings["timezone"])) - timedelta(days=1)).date()
            op = DialogueOperation(kind="intake", summary="Example вчера вечером", evidence="принял вчера вечером", certain=True, intake=Intake(name="Example", local_date=yesterday, period="evening"))
            message = await turn(db, user, "принял вчера вечером", [op])
            assert message.dialogue_cards[0]["state"] == "saved"
            row = (await db.execute(select(AICompanionEntry))).scalar_one()
            assert row.kind == "intake" and row.data["occurred_at"] is None and row.data["time_precision"] == "date"
            result = await execute_dialogue_tool(db, user.id, "find_companion_records", {"kind": "intake", "from_date": yesterday.isoformat(), "to_date": (yesterday + timedelta(days=1)).isoformat(), "query": "Example"}, False)
            assert result["ok"] and result["data"]["entries"][0]["id"] == row.id
    asyncio.run(run())


@db_test
def test_daily_prompt_stop_and_intro_once():
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            await dialogue.introduce(db, user.id)
            await dialogue.introduce(db, user.id)
            await db.commit()
            assert len(list((await db.execute(select(AIMessage))).scalars())) == 1
            await turn(db, user, "вес 84", [weight()])
            await schedule_recurring(db, profile, service.now_utc())
            await db.flush()
            reminder = (await db.execute(select(AICompanionReminder).where(AICompanionReminder.kind == "checkin"))).scalar_one()
            text = await reminder_text(db, reminder, profile)
            assert "Как самочувствие" in text and "Если сегодня измеряли вес" not in text
            assert "Что сегодня ели" not in text  # No nutrition tracking was requested.
            source = await dialogue.say(db, user.id, "не напоминай", sender=MessageSender.USER)
            await dialogue.direct_reply(db, user.id, source)
            await db.commit()
            assert profile.settings["checkin_time"] is None
            await turn(db, user, "вес 83", [weight("83")])
            assert profile.settings["checkin_time"] is None
            assert await reminder_text(db, reminder, profile) is None
    asyncio.run(run())


@db_test
def test_bare_confirmation_without_card_falls_through_to_model():
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            source = await dialogue.say(db, user.id, "Да", sender=MessageSender.USER)
            assert await dialogue.direct_reply(db, user.id, source) is None
            source = await dialogue.say(db, user.id, "Не сохраняй", sender=MessageSender.USER)
            response = await dialogue.direct_reply(db, user.id, source)
            assert response.text == "Сейчас нет карточки, ожидающей подтверждения."
    asyncio.run(run())


@db_test
def test_multiple_pending_requires_selection_and_cross_user_actions_fail():
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            message = await turn(db, user, "два измерения", [weight(certain=False), weight("83", certain=False)])
            source = await dialogue.say(db, user.id, "да", sender=MessageSender.USER)
            answer = await dialogue.direct_reply(db, user.id, source)
            assert isinstance(answer, AIMessage) and "какую карточку" in answer.text
            other = User(name="Other", surname="Test", password_hash="not-a-password")
            db.add(other); await db.flush()
            await enable(db, other)
            with pytest.raises(HTTPException) as forbidden:
                await card_action(db, other, message, "dialogue_confirm")
            assert forbidden.value.status_code == 403
    asyncio.run(run())


@db_test
def test_ios_match_block_and_erase_cleans_workflow_and_cards():
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            result = await execute_dialogue_tool(db, user.id, "match_course_products", {"query": "Example"}, False)
            assert result == {"ok": False, "error": "commerce_unavailable"}
            await turn(db, user, "вес 84", [weight()])
            await service.erase_companion(db, user.id)
            await db.commit()
            assert not list((await db.execute(select(AICompanionDialogue))).scalars())
            assert not list((await db.execute(select(AIMessage))).scalars())
            assert not list((await db.execute(select(AICompanionEntry))).scalars())
    asyncio.run(run())


@db_test
def test_course_confirmation_revision_report_and_actual_event(monkeypatch):
    now = datetime(2030, 1, 4, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(service, "now_utc", lambda: now)
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            plan = PlanData.model_validate({"name": "Мой курс", "timezone": "Europe/Moscow", "items": [{"name": "Example", "stages": [{"start_date": "2030-01-01", "end_date": "2030-01-08", "amount": 1, "unit": "mg", "times": ["10:00"]}]}]})
            op = DialogueOperation(kind="plan", summary="Мой курс", evidence="запиши мой курс", certain=True, plan=plan)
            first = await turn(db, user, "запиши мой курс", [op])
            assert first.dialogue_cards[0]["state"] == "pending"
            assert await service.current_plan(db, user.id) is None
            await card_action(db, user, first, "dialogue_confirm")
            assert (await service.profile_for(db, user.id)).settings["course_reminders"]
            checkin = AICompanionReminder(user_id=user.id, kind="checkin", dedupe_key="checkin:2030-01-04", due_at=now + timedelta(hours=6))
            db.add(checkin)
            await db.flush()
            event = (await db.execute(select(AICompanionEvent).order_by(AICompanionEvent.id).limit(1))).scalar_one()
            mark = DialogueOperation(kind="event", summary="Первый приём", evidence="принял 1 января утром", certain=True, resource_id=event.id, expected_version=event.version, status="done", intake=Intake(name="Example", local_date=date(2030, 1, 1), period="morning"))
            reply = await turn(db, user, "принял 1 января утром", [mark])
            assert reply.dialogue_cards[0]["state"] == "saved"
            assert event.status == "done" and event.occurred_at is None
            assert checkin.status == "pending"
            plan.items[0].stages[0].end_date = date(2030, 1, 9)
            revision = await turn(db, user, "продли записанную схему до 9 января", [op.model_copy(update={"evidence": "до 9 января"})])
            await card_action(db, user, revision, "dialogue_confirm")
            report = await course_report(db, user.id)
            assert report["versions"] == 2 and report["events"]["done"] == 1
            assert "всем версиям" in await quick_report(db, user.id, "course")
            assert report["events"]["skipped"] == 0
            assert checkin.status == "pending"
            await card_action(db, user, reply, "dialogue_undo")
            assert checkin.status == "pending" and event.status == "pending"
    asyncio.run(run())


@db_test
def test_catalog_match_is_noncommercial_and_new_ios_link_is_rejected():
    from src.database.models import Product, Variant
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            product = Product(name="Example", sku="example-test")
            db.add(product); await db.flush()
            variant = Variant(product_id=product.id, name="10 mg", price=100, stock=2)
            db.add(variant); await db.flush()
            result = await execute_dialogue_tool(db, user.id, "match_course_products", {"query": "Example"}, True)
            found = result["data"]["candidates"][0]
            assert found["variant_id"] == variant.id and found["package"]["amount"] == "10"
            assert not {"price", "stock", "image_url"}.intersection(found)
            plan = PlanData.model_validate({"name": "My plan", "items": [{"name": "Example", "variant_id": variant.id, "stages": [{"start_date": "2030-01-01", "end_date": "2030-01-03", "amount": 1, "unit": "mg", "times": ["10:00"]}]}]})
            reply = await turn(db, user, "мой курс", [DialogueOperation(kind="plan", summary="курс", evidence="мой курс", plan=plan)])
            assert reply.dialogue_cards[0]["state"] == "needs_correction"
            assert await service.current_plan(db, user.id) is None
    asyncio.run(run())


@db_test
def test_v2_provider_roundtrip_retry_and_no_commerce_tools(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from src.app.services.ai import chat as chat_service
    from src.database.schemas.ai.chat import AIChatWithMessagesRead
    monkeypatch.setattr(chat_service, "send_ai_reply_notification", AsyncMock())
    monkeypatch.setattr(chat_service, "record_customer_event_safe", AsyncMock())
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            seen = {}
            async def respond(**kwargs):
                seen.update(kwargs)
                await kwargs["resource_recorder"]("conversation", kwargs["conversation_id"])
                return {"text": "Проверяю запись", "structured_output": {"assistant_text": "Проверяю запись", "companion_dialogue": DialogueTurn(operations=[weight()]).model_dump(mode="json")}, "openai_model": "mock", "input_tokens": 100, "output_tokens": 10, "conversation_id": kwargs["conversation_id"]}
            professor = SimpleNamespace(create_conversation=AsyncMock(return_value="conv_mock"), send_message_v2=AsyncMock(side_effect=[RuntimeError("temporary"), None]), _resolve_model_name=lambda _: "mock")
            kwargs = dict(user=user, text="вес 84", attachments=None, professor_client=professor, allow_commerce=False, companion_profile=profile, client_request_id="dialogue-retry-001", dialogue_protocol=2)
            with pytest.raises(RuntimeError):
                await chat_service.send_user_chat_message(db, **kwargs)
            # A retry is a new HTTP request with freshly loaded auth/profile.
            await db.refresh(user)
            await db.refresh(profile)
            professor.send_message_v2 = AsyncMock(side_effect=respond)
            result = await chat_service.send_user_chat_message(db, **kwargs)
            read = AIChatWithMessagesRead.model_validate(result.chat)
            assert len(read.messages) == 2 and read.messages[-1].dialogue_cards[0]["state"] == "saved"
            assert seen["companion_context"]["dialogue"]["protocol"] == 2
            assert not {"match_course_products", "search_catalog_products", "get_catalog_product", "calculate_course_supply"}.intersection(t["name"] for t in seen["function_tools"])
            repeat = await chat_service.send_user_chat_message(db, **kwargs)
            assert len(repeat.chat.messages) == 2
            assert len(list((await db.execute(select(AICompanionEntry))).scalars())) == 1
            professor.send_message_v2.assert_awaited_once()
    asyncio.run(run())


@pytest.mark.parametrize("failure_kind", ["schema", "missing_card"])
@db_test
def test_invalid_provider_structure_is_corrected_once(monkeypatch, failure_kind):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from src.app.services.ai import chat as chat_service
    from src.database.schemas.ai.chat import AIChatWithMessagesRead
    monkeypatch.setattr(chat_service, "send_ai_reply_notification", AsyncMock())
    monkeypatch.setattr(chat_service, "record_customer_event_safe", AsyncMock())

    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            invalid = {
                "text": "" if failure_kind == "schema" else "Подтвердите запись питания.",
                "structured_output": {
                    "assistant_text": "" if failure_kind == "schema" else "Подтвердите запись питания.",
                    "product_refs": [],
                    "basket_addition": None,
                    "companion_proposals": [],
                    "companion_dialogue": None,
                },
                "openai_model": "mock",
                "input_tokens": 100,
                "cached_input_tokens": 20,
                "output_tokens": 10,
                "context_input_tokens": 100,
                "file_search_calls": 1,
                "tool_rounds": 1,
                "tool_calls": 1,
                "conversation_id": "conv_mock",
                "files": [],
            }
            corrected = {
                "text": "Запись проверена.",
                "structured_output": {
                    "assistant_text": "Запись проверена.",
                    "product_refs": [],
                    "basket_addition": None,
                    "companion_proposals": [],
                    "companion_dialogue": DialogueTurn(operations=[weight()]).model_dump(mode="json"),
                },
                "openai_model": "mock",
                "input_tokens": 120,
                "cached_input_tokens": 60,
                "output_tokens": 15,
                "context_input_tokens": 120,
                "file_search_calls": 0,
                "tool_rounds": 0,
                "tool_calls": 0,
                "conversation_id": "conv_mock",
                "files": [],
            }
            professor = SimpleNamespace(
                create_conversation=AsyncMock(return_value="conv_mock"),
                send_message_v2=AsyncMock(side_effect=[invalid, corrected]),
                _resolve_model_name=lambda _: "mock",
            )

            result = await chat_service.send_user_chat_message(
                db,
                user=user,
                text="вес 84",
                attachments=None,
                professor_client=professor,
                allow_commerce=False,
                companion_profile=profile,
                client_request_id=f"dialogue-validation-retry-{failure_kind}",
                dialogue_protocol=2,
            )

            read = AIChatWithMessagesRead.model_validate(result.chat)
            assert len(read.messages) == 2
            assert read.messages[-1].text == "Запись проверена."
            assert read.messages[-1].dialogue_cards[0]["state"] == "saved"
            assert result.turn_meta["input_tokens"] == 220
            assert result.turn_meta["cached_input_tokens"] == 80
            assert result.turn_meta["output_tokens"] == 25
            assert professor.send_message_v2.await_count == 2
            retry_call = professor.send_message_v2.await_args_list[1].kwargs
            assert "не прошёл серверную валидацию" in retry_call["input_text"]
            if failure_kind == "missing_card":
                assert "confirmation card" in retry_call["input_text"]
            assert retry_call["conversation_id"] == "conv_mock"
            assert retry_call["function_tools"] == []
            assert retry_call["file_contents"] == []
            assert retry_call["image_contents"] == []

    asyncio.run(run())


@db_test
def test_deleted_entry_can_be_restored_and_old_snapshot_is_not_exposed():
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            await turn(db, user, "вес 84", [weight()])
            row = (await db.execute(select(AICompanionEntry))).scalar_one()
            original_id = row.id
            deletion = await turn(db, user, "удали запись", [DialogueOperation(kind="delete_entry", summary="Удалить измерение", evidence="удали запись", resource_id=row.id, expected_version=row.version)])
            assert deletion.dialogue_cards[0]["state"] == "pending"
            await card_action(db, user, deletion, "dialogue_confirm")
            assert not list((await db.execute(select(AICompanionEntry))).scalars())
            await card_action(db, user, deletion, "dialogue_undo")
            restored = (await db.execute(select(AICompanionEntry))).scalar_one()
            assert restored.id == original_id and restored.data["weight_kg"] == "84"
    asyncio.run(run())


@db_test
def test_linked_changes_share_one_confirmation_and_keep_course_reminders():
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            plan = PlanData.model_validate({"name": "Курс", "items": [{"name": "Example", "stages": [{"start_date": "2030-01-01", "end_date": "2030-01-03", "amount": 1, "unit": "mg", "times": ["10:00"]}]}]})
            settings = Settings.model_validate(profile.settings)
            settings.checkin_time = time(20)
            reply = await turn(db, user, "курс, спрашивай в 20", [
                DialogueOperation(kind="plan", summary="Курс", evidence="курс", plan=plan),
                DialogueOperation(kind="settings", summary="Вопрос в 20", evidence="спрашивай в 20", settings=settings),
            ])
            assert len(reply.dialogue_cards) == 1 and reply.dialogue_cards[0]["kind"] == "batch"
            await card_action(db, user, reply, "dialogue_confirm")
            assert await service.current_plan(db, user.id) is not None
            assert profile.settings["checkin_time"] == "20:00:00" and profile.settings["course_reminders"]
    asyncio.run(run())


@db_test
def test_pending_card_survives_many_other_messages():
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            first = await turn(db, user, "проверь измерение", [weight(certain=False)])
            for _ in range(205):
                await dialogue.say(db, user.id, "Нейтральный ответ", {"dialogue_cards": []})
            await db.commit()
            pending = await dialogue.pending_cards(db, user.id)
            assert len(pending) == 1 and pending[0][0].id == first.id
    asyncio.run(run())


@db_test
def test_dialogue_migration_roundtrip():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect, text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    async def run():
        engine = create_async_engine(URL, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                await connection.execute(text("CREATE TABLE users (id BIGINT PRIMARY KEY)"))
                await connection.execute(text("CREATE TABLE ai_messages (id BIGINT PRIMARY KEY)"))
                def migrate(sync):
                    path = Path(__file__).parents[1] / "migrations/versions/b3d5f7a9c1e3_companion_dialogue.py"
                    spec = importlib.util.spec_from_file_location("dialogue_migration", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    with Operations.context(MigrationContext.configure(sync)):
                        module.upgrade()
                        assert "ai_companion_dialogues" in inspect(sync).get_table_names()
                        assert {"draft", "focus", "last_hint_at"} <= {c["name"] for c in inspect(sync).get_columns("ai_companion_dialogues")}
                        module.downgrade()
                        assert "ai_companion_dialogues" not in inspect(sync).get_table_names()
                await connection.run_sync(migrate)
                await transaction.rollback()
        finally:
            await engine.dispose()
    asyncio.run(run())
