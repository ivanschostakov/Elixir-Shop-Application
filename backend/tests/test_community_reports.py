import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.requests import Request

from config import ufa_now
from src.app.main import app
from src.app.services import community, community_reports
from src.database.models import CommunityAuthor, CommunityMessage, CommunityReport, CommunityTopic, User
from src.database.schemas.community import CommunityReportPayload
from test_ai_companion_db import URL, database

REQUEST = Request({"type": "http", "method": "POST", "scheme": "https", "path": "/", "headers": [], "server": ("example.test", 443)})
db_test = pytest.mark.skipif(not URL, reason="Set an isolated COMPANION_TEST_DB_URL")


@pytest.fixture
def allowed(monkeypatch):
    monkeypatch.setattr(community, "require_community_access", AsyncMock())
    monkeypatch.setattr(community, "TELEGRAM_COMMUNITY_CHAT_ID", -100123)
    monkeypatch.setattr(community_reports, "enforce_rate_limit", AsyncMock())


async def seed(db):
    writer = User(name="Writer", surname="Member", password_hash="test")
    db.add(writer); await db.flush()
    topic = CommunityTopic(telegram_chat_id=-100123, telegram_thread_id=1, name="Discussion")
    author = CommunityAuthor(kind="app", telegram_peer_id=writer.id, app_user_id=writer.id, full_name="Writer")
    db.add_all([topic, author]); await db.flush()
    message = CommunityMessage(topic_id=topic.id, author_id=author.id, app_user_id=writer.id, source="app", text="Reported content", sent_at=ufa_now())
    db.add(message); await db.flush()
    topic.last_message_id = message.id
    return writer, topic, message


async def report(db, viewer, topic, message):
    return await community_reports.report_community_message(db, user=viewer, request=REQUEST, topic_id=topic.id, message_id=message.id, payload=CommunityReportPayload(reason="harassment", details="Please review"))


@db_test
def test_report_is_persistent_and_idempotent(allowed):
    async def run():
        async with database() as (db, viewer):
            _, topic, message = await seed(db)
            receipt = await report(db, viewer, topic, message)
            duplicate = await report(db, viewer, topic, message)
            assert receipt == duplicate and receipt.status == "pending"
            rows = (await db.execute(select(CommunityReport))).scalars().all()
            assert len(rows) == 1
            assert rows[0].reason == "harassment" and rows[0].details == "Please review"
            assert rows[0].reporter_id == viewer.id and rows[0].message_id == message.id
    asyncio.run(run())


@db_test
def test_report_rejects_own_hidden_deleted_and_foreign_topic_messages(allowed):
    async def run():
        async with database() as (db, viewer):
            writer, topic, message = await seed(db)
            with pytest.raises(HTTPException) as error:
                await report(db, writer, topic, message)
            assert error.value.status_code == 422
            for field, value in (("is_hidden", True), ("is_deleted", True), ("telegram_chat_id", -999)):
                original = getattr(topic, field)
                setattr(topic, field, value); await db.flush()
                with pytest.raises(HTTPException) as error:
                    await report(db, viewer, topic, message)
                assert error.value.status_code == 404
                setattr(topic, field, original); await db.flush()
            message.deleted_at = ufa_now(); await db.flush()
            with pytest.raises(HTTPException) as error:
                await report(db, viewer, topic, message)
            assert error.value.status_code == 404
    asyncio.run(run())


def test_reporting_requires_login_and_valid_payload():
    assert TestClient(app).post("/api/v1/users/me/community/topics/1/messages/1/reports", json={"reason": "spam"}).status_code == 401
    from pydantic import ValidationError
    for payload in ({"reason": "unknown"}, {"reason": "spam", "details": "x" * 1001}):
        with pytest.raises(ValidationError):
            CommunityReportPayload.model_validate(payload)


@db_test
def test_report_migration_matches_model_and_can_be_reversed():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    async def run():
        async with database() as (db, _):
            def migrate(connection):
                CommunityReport.__table__.drop(connection)
                path = Path("migrations/versions/f7b9d1e3a5c7_add_community_reports.py")
                spec = importlib.util.spec_from_file_location("report_migration", path)
                migration = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration)
                migration.op = Operations(MigrationContext.configure(connection))
                migration.upgrade()
                schema = inspect(connection)
                assert {c["name"] for c in schema.get_columns("community_reports")} == set(CommunityReport.__table__.columns.keys())
                assert {c["name"] for c in schema.get_unique_constraints("community_reports")} == {"uq_community_reports_reporter_message"}
                assert len(schema.get_foreign_keys("community_reports")) == 3
                migration.downgrade()
                assert not inspect(connection).has_table("community_reports")
            await (await db.connection()).run_sync(migrate)
    asyncio.run(run())
