import asyncio
import importlib.util
import warnings
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import BigInteger, Column, MetaData, Table, create_engine, delete, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.app.services.community import notification_settings as settings
from src.database.models import CommunityNotificationMute, CommunityTopic
from src.database.schemas.community import CommunityNotificationUpdate


class AsyncAdapter:
    """Exercise the real ORM queries against SQLite without an external server."""
    def __init__(self, session):
        self.session = session
        self.next_id = 0

    async def execute(self, statement): return self.session.execute(statement)
    async def get(self, model, identity): return self.session.get(model, identity)
    async def commit(self): self.session.commit()

    def add(self, row):
        if row.id is None:
            self.next_id += 1
            row.id = self.next_id  # SQLite does not autoincrement BIGINT keys.
        self.session.add(row)


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_COMMUNITY_CHAT_ID", -10099)
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    metadata = MetaData()
    users = Table("users", metadata, Column("id", BigInteger, primary_key=True))
    Table("community_messages", metadata, Column("id", BigInteger, primary_key=True))
    CommunityTopic.__table__.to_metadata(metadata)
    CommunityNotificationMute.__table__.to_metadata(metadata)
    metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.execute(users.insert(), [{"id": 1}, {"id": 2}])
        session.add_all([
            CommunityTopic(id=101, telegram_chat_id=-10099, telegram_thread_id=1, name="First"),
            CommunityTopic(id=102, telegram_chat_id=-10099, telegram_thread_id=2, name="Second"),
            CommunityTopic(id=103, telegram_chat_id=-20099, telegram_thread_id=1, name="Other group"),
        ])
        session.commit()
        yield AsyncAdapter(session)
    engine.dispose()


def test_group_switch_preserves_topic_choices_and_is_scoped_to_the_account(db):
    async def run():
        first, second = SimpleNamespace(id=1), SimpleNamespace(id=2)
        assert (await settings.get_community_notification_settings(db, user=first)).model_dump() == {"muted": False, "muted_topic_ids": []}
        await settings.set_community_notification_muted(db, user=first, muted=True, topic_id=101)
        muted = await settings.set_community_notification_muted(db, user=first, muted=True)
        assert muted.muted and muted.muted_topic_ids == [101]
        resumed = await settings.set_community_notification_muted(db, user=first, muted=False)
        assert not resumed.muted and resumed.muted_topic_ids == [101]
        muted = await settings.set_community_notification_muted(db, user=first, muted=True, topic_id=102)
        assert muted.muted_topic_ids == [101, 102]
        assert (await settings.get_community_notification_settings(db, user=second)).muted_topic_ids == []
        restored = await settings.set_community_notification_muted(db, user=first, muted=False, topic_id=101)
        assert restored.muted_topic_ids == [102]
    asyncio.run(run())


@pytest.mark.parametrize("topic_id", [None, 101])
def test_duplicate_mute_and_unmute_requests_are_idempotent(db, topic_id):
    async def run():
        user = SimpleNamespace(id=1)
        for _ in range(2): await settings.set_community_notification_muted(db, user=user, muted=True, topic_id=topic_id)
        assert db.session.scalar(select(func.count(CommunityNotificationMute.id))) == 1
        for _ in range(2): await settings.set_community_notification_muted(db, user=user, muted=False, topic_id=topic_id)
        assert db.session.scalar(select(func.count(CommunityNotificationMute.id))) == 0
    asyncio.run(run())


@pytest.mark.parametrize("topic_id,flag", [(999, None), (103, None), (101, "is_hidden"), (101, "is_deleted")])
def test_foreign_hidden_deleted_and_missing_topics_are_rejected(db, topic_id, flag):
    if flag:
        setattr(db.session.get(CommunityTopic, topic_id), flag, True)
        db.session.commit()
    with pytest.raises(HTTPException) as error:
        asyncio.run(settings.set_community_notification_muted(db, user=SimpleNamespace(id=1), muted=True, topic_id=topic_id))
    assert error.value.status_code == 404
    assert db.session.scalar(select(func.count(CommunityNotificationMute.id))) == 0


def test_unique_group_mute_and_foreign_key_cleanup(db):
    asyncio.run(settings.set_community_notification_muted(db, user=SimpleNamespace(id=1), muted=True))
    db.session.add(CommunityNotificationMute(id=999, user_id=1, telegram_chat_id=-10099, topic_id=None))
    with pytest.raises(IntegrityError): db.session.commit()
    db.session.rollback()
    asyncio.run(settings.set_community_notification_muted(db, user=SimpleNamespace(id=1), muted=True, topic_id=101))
    db.session.execute(delete(CommunityTopic).where(CommunityTopic.id == 101))
    db.session.commit()
    assert db.session.scalar(select(func.count(CommunityNotificationMute.id))) == 1
    users = db.session.bind.dialect.identifier_preparer.quote("users")
    from sqlalchemy import text
    db.session.execute(text(f"DELETE FROM {users} WHERE id=1"))
    db.session.commit()
    assert db.session.scalar(select(func.count(CommunityNotificationMute.id))) == 0


@pytest.mark.parametrize("payload", [{}, {"muted": "false"}, {"muted": 1}, {"muted": True, "user_id": 2}])
def test_settings_payload_cannot_override_another_account(payload):
    with pytest.raises(ValidationError): CommunityNotificationUpdate.model_validate(payload)


def test_migration_generates_postgres_constraints_and_partial_index():
    path = Path(__file__).parents[1] / "migrations/versions/f5b7d9e1a3c6_community_notification_mutes.py"
    spec = importlib.util.spec_from_file_location("community_notification_mute_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    output = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    with Operations.context(context): migration.upgrade()
    sql = output.getvalue()
    assert "WHERE topic_id IS NULL" in sql
    assert "UNIQUE (user_id, topic_id)" in sql
    assert "REFERENCES users (id) ON DELETE CASCADE" in sql


def test_migration_revision_is_unique_and_extends_existing_chain():
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        revisions = list(ScriptDirectory(str(Path(__file__).parents[1] / "migrations")).walk_revisions())
    ids = [revision.revision for revision in revisions]
    assert len(ids) == len(set(ids))
    notification_revision = next(revision for revision in revisions if revision.revision == "f5b7d9e1a3c6")
    assert notification_revision.down_revision == "e4a6c8e0f2b4"
