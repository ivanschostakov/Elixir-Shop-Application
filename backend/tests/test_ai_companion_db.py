"""Opt-in integration tests; never connect to the application's configured DB.

COMPANION_TEST_DB_URL must name a disposable database called companion_test.
All changes roll back. A temporary PostgreSQL instance is recommended.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

import config
from src.database import Base
from src.database.models import AIChat, AIMessage, Attachment, User
from src.database.models.ai.companion import AICompanionEntry, AICompanionEvent, AICompanionOperation, AICompanionPlan, AICompanionProfile, AICompanionReminder, AIProviderResource
from src.app.services.ai.companion import service
from src.app.services.ai.companion.jobs import deliver_reminder, schedule_recurring
from src.app.services.ai.companion.schemas import Action, EntryData, Nutrition, PlanData, ProfileData, Proposal, Settings
from src.integrations.ai.enums import MessageSender

URL = os.environ.get("COMPANION_TEST_DB_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Set an isolated COMPANION_TEST_DB_URL")


@asynccontextmanager
async def database():
    assert URL and make_url(URL).database == "companion_test", "Only a disposable companion_test DB is allowed"
    engine = create_async_engine(URL, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            await connection.run_sync(Base.metadata.create_all)
            async with AsyncSession(connection, expire_on_commit=False, autoflush=False, join_transaction_mode="create_savepoint") as db:
                user = User(name="Test", surname="Companion", password_hash="not-a-password")
                db.add(user)
                await db.flush()
                yield db, user
            await transaction.rollback()
    finally:
        await engine.dispose()


async def act(db, user, kind, **kwargs):
    result = await service.apply_action(db, user.id, Action(request_key=str(uuid4()), kind=kind, **kwargs))
    await db.commit()
    return result


async def enable(db, user):
    await act(db, user, "enable", consent_version=config.AI_COMPANION_CONSENT_VERSION, adult_confirmed=True)
    return await service.profile_for(db, user.id)


def test_nutrition_eligibility_confirmation_history_and_stale_draft(monkeypatch):
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    monkeypatch.setattr(config, "AI_COMPANION_NUTRITION_RULES_JSON", "")
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            await act(db, user, "profile", expected_version=profile.version, profile=ProfileData(age=30, sex="male", height_cm=180, activity="low"))
            await act(db, user, "entry", entry=EntryData(kind="weight", weight_kg=90, occurred_at=datetime.now(timezone.utc)))
            assert not (await service.nutrition_suggestion(db, user.id))["available"]
            await act(db, user, "settings", expected_version=profile.version, settings=Settings(nutrition_auto_eligible=True))
            result = await service.nutrition_suggestion(db, user.id)
            assert result["available"] and profile.data["nutrition"] is None  # Read-only suggestion.
            nutrition = Nutrition.model_validate({k: float(v) for k, v in result["nutrition"].items()})
            await act(db, user, "nutrition", expected_version=profile.version, nutrition=nutrition, nutrition_rule_version=result["rule_version"])
            assert profile.data["nutrition_source"] == "calculated" and len(profile.target_history) == 1
            saved = profile.data["nutrition"]
            await act(db, user, "entry", entry=EntryData(kind="weight", weight_kg=95, occurred_at=datetime.now(timezone.utc)))
            assert profile.data["nutrition"] == saved  # New weight cannot silently change a goal.
            with pytest.raises(HTTPException) as stale:
                await act(db, user, "nutrition", expected_version=profile.version, nutrition=nutrition, nutrition_rule_version=result["rule_version"])
            assert stale.value.status_code == 409
            await act(db, user, "settings", expected_version=profile.version, settings=Settings(nutrition_auto_eligible=False))
            assert not (await service.nutrition_suggestion(db, user.id))["available"]
            with pytest.raises(HTTPException) as revoked:
                await act(db, user, "nutrition", expected_version=profile.version, nutrition=nutrition, nutrition_rule_version=result["rule_version"])
            assert revoked.value.status_code == 409
            await act(db, user, "nutrition", expected_version=profile.version, nutrition=nutrition)
            assert profile.data["nutrition_source"] == "manual" and len(profile.target_history) == 2
    asyncio.run(run())


def test_nutrition_requires_recent_weight_and_excludes_future_measurements(monkeypatch):
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    monkeypatch.setattr(config, "AI_COMPANION_NUTRITION_RULES_JSON", "")
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            await act(db, user, "profile", expected_version=profile.version, profile=ProfileData(age=30, sex="male", height_cm=180, activity="low"))
            await act(db, user, "settings", expected_version=profile.version, settings=Settings(nutrition_auto_eligible=True))
            now = datetime.now(timezone.utc)
            for at in (now - timedelta(days=31), now + timedelta(minutes=4)):
                await act(db, user, "entry", entry=EntryData(kind="weight", weight_kg=100, occurred_at=at))
            assert not (await service.nutrition_suggestion(db, user.id))["available"]
            await act(db, user, "entry", entry=EntryData(kind="weight", weight_kg=90, occurred_at=now))
            assert (await service.nutrition_suggestion(db, user.id))["nutrition"]["kcal"] == "1918"
    asyncio.run(run())


def test_actions_idempotency_scope_and_totals(monkeypatch):
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            now = datetime.now(timezone.utc)
            payload = Action(request_key="repeat-entry-01", kind="entry", entry=EntryData(kind="meal", occurred_at=now, name="Example", nutrition=Nutrition(kcal=500, protein=20, fat=10, carbs=80)))
            await service.apply_action(db, user.id, payload); await db.commit()
            await service.apply_action(db, user.id, payload); await db.commit()
            rows = await service.entries_for(db, user.id, now - timedelta(days=1), now + timedelta(days=1))
            assert len(rows) == 1
            summary = await service.summary_for(db, user.id, now - timedelta(days=1), now + timedelta(days=1))
            assert summary["nutrition"]["kcal"] == "500" and summary["weight_change_kg"] is None
            with pytest.raises(HTTPException) as error:
                await service.apply_action(db, user.id, payload.model_copy(update={"kind": "delete_entry"}))
            assert error.value.status_code == 409
            entry_id, entry_version = rows[0].id, rows[0].version
            await db.rollback()
            foreign = User(name="Other", surname="User", password_hash="fake")
            db.add(foreign); await db.flush(); await enable(db, foreign)
            with pytest.raises(HTTPException) as error:
                await act(db, foreign, "delete_entry", resource_id=entry_id, expected_version=entry_version)
            assert error.value.status_code == 404
    asyncio.run(run())


def test_plan_revision_reminders_and_erasure(monkeypatch):
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            await act(db, user, "settings", expected_version=profile.version, settings=Settings(course_reminders=True))
            day = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
            plan = PlanData.model_validate({"name": "User plan", "items": [{"name": "Example", "home_amount": 3, "package_amount": 5, "package_unit": "mg", "stages": [{"start_date": day, "end_date": day, "amount": 1, "unit": "mg", "times": ["12:00"]}]}]})
            profile = await service.profile_for(db, user.id)
            await act(db, user, "plan", expected_version=profile.version, plan=plan)
            first = await service.current_plan(db, user.id)
            events = list((await db.execute(select(AICompanionEvent))).scalars())
            assert len(events) == 1
            reminders = list((await db.execute(select(AICompanionReminder).where(AICompanionReminder.status == "pending"))).scalars())
            assert len(reminders) == 1
            first_id, event_id = first.id, events[0].id
            with pytest.raises(HTTPException):
                await act(db, user, "event", resource_id=events[0].id, expected_version=1, status="done")
            await db.rollback()
            await db.refresh(user)
            profile = await service.profile_for(db, user.id)
            await act(db, user, "plan", expected_version=profile.version, plan=plan)
            second = await service.current_plan(db, user.id)
            assert second.id != first_id and second.version == 2
            old_event = await db.get(AICompanionEvent, event_id)
            await db.refresh(old_event)
            assert old_event.status == "cancelled"
            state = await service.get_state(db, user.id)
            assert len(state["events"]) == 1
            assert (await service.context_for(db, user.id))["profile_version"] == state["profile"]["version"]
            chat = AIChat(user_id=user.id, conversation_id="conv_sensitive")
            db.add(chat); await db.flush()
            db.add(AIMessage(user_id=user.id, chat_id=chat.id, sender=MessageSender.AI, text="private", is_sensitive=True))
            await service.register_resource(db, user.id, "file", "file_sensitive"); await db.commit()
            await service.erase_companion(db, user.id); await db.commit()
            assert await service.profile_for(db, user.id) is None
            assert not list((await db.execute(select(AIMessage))).scalars())
            assert {r.kind for r in (await db.execute(select(AIProviderResource).where(AIProviderResource.status == "pending_delete"))).scalars()} == {"file", "conversation"}
            assert chat.conversation_id.startswith("reset:")
    asyncio.run(run())


def test_cards_require_confirmation_and_reject_stale_profile(monkeypatch):
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            chat = AIChat(user_id=user.id, conversation_id="conv_draft")
            db.add(chat); await db.flush()
            message = AIMessage(user_id=user.id, chat_id=chat.id, sender=MessageSender.AI, text="draft")
            db.add(message); await db.flush()
            proposal = Proposal(kind="entry", summary="weight", entry=EntryData(kind="weight", occurred_at=datetime.now(timezone.utc), weight_kg=80))
            await service.attach_proposals(db, user.id, message, [proposal], profile)
            await db.commit()
            assert not list((await db.execute(select(AICompanionEntry))).scalars())
            card = message.companion_cards[0]
            await act(db, user, "confirm", message_id=message.id, action_id=card["id"], action_token=card["action_token"])
            assert len(list((await db.execute(select(AICompanionEntry))).scalars())) == 1
            await db.refresh(message)
            assert message.companion_cards[0]["state"] == "confirmed"
            with pytest.raises(HTTPException) as error:
                await act(db, user, "confirm", message_id=message.id, action_id=card["id"], action_token=card["action_token"])
            assert error.value.status_code == 409
    asyncio.run(run())


def test_recurring_is_deduplicated_and_available_without_push(monkeypatch):
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            now = datetime.now(timezone.utc)
            profile.created_at = now - timedelta(days=1)
            profile.settings = Settings(timezone="UTC", daily_time=(now - timedelta(minutes=1)).time().replace(tzinfo=None)).model_dump(mode="json")
            await db.flush()
            await schedule_recurring(db, profile, now); await db.flush()
            await schedule_recurring(db, profile, now); await db.flush()
            rows = list((await db.execute(select(AICompanionReminder))).scalars())
            assert len(rows) == 1
            await deliver_reminder(db, rows[0], profile, now); await db.flush()
            assert rows[0].status == "sent" and rows[0].message_id
            messages = list((await db.execute(select(AIMessage))).scalars())
            assert len(messages) == 1 and messages[0].is_sensitive
    asyncio.run(run())


def test_companion_turn_persists_draft_private_upload_and_deduplicates(monkeypatch, tmp_path):
    from io import BytesIO
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from starlette.datastructures import UploadFile
    from src.app.services.ai import chat as chat_service
    from src.database.schemas.ai.chat import AIChatWithMessagesRead
    import src.database.models.ai.attachment as attachment_model
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    monkeypatch.setattr(attachment_model, "PRIVATE_MEDIA_DIR", tmp_path)
    monkeypatch.setattr(chat_service, "send_ai_reply_notification", AsyncMock())
    monkeypatch.setattr(chat_service, "record_customer_event_safe", AsyncMock())
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            entry = EntryData(kind="weight", occurred_at=datetime.now(timezone.utc), weight_kg=80)
            seen = {}
            async def respond(**kwargs):
                seen.update(kwargs)
                await kwargs["resource_recorder"]("conversation", kwargs["conversation_id"])
                await kwargs["resource_recorder"]("response", "resp_mock")
                return {"text": "Проверьте вес", "structured_output": {"assistant_text": "Проверьте вес", "companion_proposals": [Proposal(kind="entry", entry=entry, summary="Записать вес").model_dump(mode="json")]}, "openai_model": "mock", "input_tokens": 100, "output_tokens": 10, "conversation_id": kwargs["conversation_id"]}
            professor = SimpleNamespace(create_conversation=AsyncMock(return_value="conv_mock"), send_message_v2=AsyncMock(side_effect=respond), _resolve_model_name=lambda _: "mock")
            result = await chat_service.send_user_chat_message(db, user=user, text="Вес 80 кг", attachments=[UploadFile(file=BytesIO(b"private attachment"), filename="note.txt")], professor_client=professor, allow_commerce=False, companion_profile=profile, client_request_id="request-turn-001")
            read = AIChatWithMessagesRead.model_validate(result.chat)
            assert len(read.messages) == 2
            assert len(read.messages[-1].companion_cards) == 1
            assert not list((await db.execute(select(AICompanionEntry))).scalars())
            attachment = read.messages[0].attachments[0]
            assert attachment.is_private and "/attachments/" in attachment.download_path
            assert seen["input_text"] == "Вес 80 кг"
            assert "companion_context" in seen and not seen["companion_context"]["commerce_allowed"]
            assert "calculate_course_supply" not in {t["name"] for t in seen["function_tools"]}
            repeat = await chat_service.send_user_chat_message(db, user=user, text="Вес 80 кг", attachments=None, professor_client=professor, allow_commerce=False, companion_profile=profile, client_request_id="request-turn-001")
            assert len(repeat.chat.messages) == 2
            professor.send_message_v2.assert_awaited_once()
    asyncio.run(run())


def test_migration_upgrade_downgrade_on_minimal_previous_schema():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect, text
    async def run():
        assert URL and make_url(URL).database == "companion_test"
        engine = create_async_engine(URL, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                await connection.execute(text("CREATE TABLE users (id BIGINT PRIMARY KEY)"))
                await connection.execute(text("CREATE TABLE ai_messages (id BIGINT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id))"))
                await connection.execute(text("CREATE TABLE attachments (id BIGINT PRIMARY KEY)"))
                def migrate(sync):
                    path = Path(__file__).parents[1] / "migrations/versions/a2c4e6f8b0d2_add_ai_companion.py"
                    spec = importlib.util.spec_from_file_location("companion_migration", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    with Operations.context(MigrationContext.configure(sync)):
                        module.upgrade()
                        assert "ai_companion_profiles" in inspect(sync).get_table_names()
                        assert "is_sensitive" in {c["name"] for c in inspect(sync).get_columns("ai_messages")}
                        module.downgrade()
                        assert "ai_companion_profiles" not in inspect(sync).get_table_names()
                        assert {c["name"] for c in inspect(sync).get_columns("ai_messages")} == {"id", "user_id"}
                await connection.run_sync(migrate)
                await transaction.rollback()
        finally:
            await engine.dispose()
    asyncio.run(run())


def test_erasure_during_generation_cannot_restore_health_messages(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from src.app.services.ai import chat as chat_service
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    monkeypatch.setattr(chat_service, "record_customer_event_safe", AsyncMock())
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            user_id = user.id
            async def respond(**kwargs):
                await kwargs["resource_recorder"]("conversation", kwargs["conversation_id"])
                await service.erase_companion(db, user_id)
                await db.commit()
                return {"text": "must not persist", "structured_output": {"assistant_text": "must not persist"}, "openai_model": "mock", "conversation_id": kwargs["conversation_id"]}
            professor = SimpleNamespace(create_conversation=AsyncMock(return_value="conv_inflight"), send_message_v2=respond, _resolve_model_name=lambda _: "mock")
            with pytest.raises(HTTPException) as error:
                await chat_service.send_user_chat_message(db, user=user, text="sensitive", attachments=None, professor_client=professor, companion_profile=profile, client_request_id="request-delete-race")
            assert error.value.status_code == 409
            assert not list((await db.execute(select(AIMessage).where(AIMessage.user_id == user_id))).scalars())
            chat = (await db.execute(select(AIChat).where(AIChat.user_id == user_id))).scalar_one()
            assert chat.conversation_id.startswith("reset:")
    asyncio.run(run())


def test_pause_cancels_future_and_stale_profile_card_is_rejected(monkeypatch):
    from src.app.services.ai.companion.schemas import ProfileData
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            chat = AIChat(user_id=user.id, conversation_id="conv_stale")
            db.add(chat); await db.flush()
            message = AIMessage(user_id=user.id, chat_id=chat.id, sender=MessageSender.AI, text="draft")
            db.add(message); await db.flush()
            await service.attach_proposals(db, user.id, message, [Proposal(kind="profile", summary="profile", profile=ProfileData(age=30))], profile)
            await db.commit()
            card = message.companion_cards[0]
            await act(db, user, "profile", expected_version=profile.version, profile=ProfileData(age=40))
            with pytest.raises(HTTPException) as error:
                await act(db, user, "confirm", message_id=message.id, action_id=card["id"], action_token=card["action_token"])
            assert error.value.status_code == 409
            # Failed confirmation has no partial writes.
            assert (await service.profile_for(db, user.id)).data["age"] == 40
            day = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
            plan = PlanData.model_validate({"name": "Pause", "items": [{"name": "Example", "stages": [{"start_date": day, "end_date": day, "amount": 1, "unit": "mg", "times": ["12:00"]}]}]})
            profile = await service.profile_for(db, user.id)
            await act(db, user, "plan", expected_version=profile.version, plan=plan)
            await act(db, user, "plan_status", expected_version=profile.version, status="paused")
            events = list((await db.execute(select(AICompanionEvent))).scalars())
            assert all(event.status == "cancelled" for event in events)
            assert not (await service.supply_for(db, user.id))["available"]
    asyncio.run(run())


def test_account_deletion_queues_companion_erasure(monkeypatch):
    from unittest.mock import AsyncMock
    from starlette.requests import Request
    from src.app.services.auth import service as auth
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    monkeypatch.setattr(auth, "_apply_auth_rate_limit", AsyncMock())
    monkeypatch.setattr(auth, "revoke_active_user_sessions", AsyncMock())
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            user_id = user.id
            await service.register_resource(db, user_id, "file", "file_account")
            await db.commit()
            await auth.delete_user_account(Request({"type": "http", "headers": []}), user, db)
            assert not user.is_active
            assert await service.profile_for(db, user_id) is None
            resource = (await db.execute(select(AIProviderResource))).scalar_one()
            assert resource.status == "pending_delete"
    asyncio.run(run())
