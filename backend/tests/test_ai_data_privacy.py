import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.datastructures import UploadFile
from starlette.requests import Request

from src.app.main import app
from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me import ai_chat as routes
from src.app.services.ai import chat as chat_service
from src.app.services.ai.data_consent import AI_DATA_CONSENT_VERSION, AIDataConsentPayload, get_ai_data_consent, require_ai_data_consent, set_ai_data_consent
from src.app.services.ai.private_attachments import PublicMediaFiles, migrate_legacy_ai_files
from src.database import get_db
from src.database.models import AIChat, AIMessage, Attachment, CustomerConsent, User
from src.database.schemas.ai.attachment import AIAttachmentRead
from src.integrations.ai.enums import AttachmentType, MessageSender
from test_ai_companion_db import URL, database

db_test = pytest.mark.skipif(not URL, reason="Set an isolated COMPANION_TEST_DB_URL")
REQUEST = Request({"type": "http", "method": "POST", "scheme": "https", "path": "/", "headers": [], "server": ("example.test", 443)})


def test_static_media_blocks_old_ai_urls_even_for_existing_files(tmp_path):
    (tmp_path / "attachments" / "8").mkdir(parents=True)
    (tmp_path / "attachments" / "8" / "secret.txt").write_text("private")
    (tmp_path / "products").mkdir()
    (tmp_path / "products" / "public.txt").write_text("public")
    test_app = FastAPI()
    test_app.mount("/media", PublicMediaFiles(directory=tmp_path))
    client = TestClient(test_app)
    for path in ("attachments/8/secret.txt", "%61ttachments/8/secret.txt", "products/../attachments/8/secret.txt", "attachments/8/secret.txt?v=1"):
        response = client.get("/media/" + path)
        assert response.status_code == 404 and "private" not in response.text
        assert response.headers["cache-control"] == "no-store"
    assert client.get("/media/products/public.txt").text == "public"


def test_legacy_migration_preserves_files_is_idempotent_and_refuses_collisions(tmp_path):
    source, target = tmp_path / "public", tmp_path / "private"
    (source / "5").mkdir(parents=True)
    (source / "5" / "note.txt").write_text("private attachment")
    assert migrate_legacy_ai_files(source, target) == 1
    assert (target / "5" / "note.txt").read_text() == "private attachment"
    assert not (source / "5" / "note.txt").exists()
    assert migrate_legacy_ai_files(source, target) == 0
    (source / "5").mkdir()
    (source / "5" / "note.txt").write_text("private attachment")
    assert migrate_legacy_ai_files(source, target) == 1
    (source / "5").mkdir()
    (source / "5" / "note.txt").write_text("different")
    with pytest.raises(ValueError):
        migrate_legacy_ai_files(source, target)
    assert (source / "5" / "note.txt").read_text() == "different"
    assert (target / "5" / "note.txt").read_text() == "private attachment"


def test_migration_does_not_follow_symlinks(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("unchanged")
    (source / "linked").symlink_to(outside)
    with pytest.raises(ValueError):
        migrate_legacy_ai_files(source, tmp_path / "private")
    assert outside.read_text() == "unchanged"


@db_test
def test_consent_is_explicit_versioned_revocable_and_separate_from_journal():
    async def run():
        async with database() as (db, user):
            db.add(CustomerConsent(user_id=user.id, purpose="ai_companion", channel="app", is_granted=True, policy_version="old"))
            await db.flush()
            assert not (await get_ai_data_consent(db, user.id))["granted"]
            with pytest.raises(HTTPException) as error:
                await require_ai_data_consent(db, user.id)
            assert error.value.status_code == 403
            with pytest.raises(HTTPException) as error:
                await set_ai_data_consent(db, user.id, AIDataConsentPayload(granted=True, version="outdated"))
            assert error.value.status_code == 409
            for _ in range(2):
                assert (await set_ai_data_consent(db, user.id, AIDataConsentPayload(granted=True, version=AI_DATA_CONSENT_VERSION)))["granted"]
            rows = (await db.execute(select(CustomerConsent).where(CustomerConsent.purpose == "ai_data_sharing"))).scalars().all()
            assert len(rows) == 1 and rows[0].granted_at
            await require_ai_data_consent(db, user.id)
            assert not (await set_ai_data_consent(db, user.id, AIDataConsentPayload(granted=False, version="outdated")))["granted"]
            assert rows[0].revoked_at
            with pytest.raises(HTTPException):
                await require_ai_data_consent(db, user.id)
    asyncio.run(run())


@db_test
def test_no_consent_means_no_openai_calls_or_attachment_writes(tmp_path, monkeypatch):
    import src.database.models.ai.attachment as storage
    monkeypatch.setattr(storage, "ATTACHMENTS_DIR", tmp_path)
    async def run():
        async with database() as (db, user):
            provider = SimpleNamespace(create_conversation=AsyncMock(), send_message_v2=AsyncMock(), transcribe_audio_bytes=AsyncMock())
            upload = UploadFile(file=BytesIO(b"private"), filename="private.txt")
            with pytest.raises(HTTPException) as error:
                await chat_service.send_user_chat_message(db, user=user, text="private text", attachments=[upload], professor_client=provider)
            assert error.value.status_code == 403
            with pytest.raises(HTTPException) as error:
                await routes.transcribe_my_ai_chat_voice_message(REQUEST, upload, db, user, provider)
            assert error.value.status_code == 403
            assert not list(tmp_path.iterdir())
            provider.create_conversation.assert_not_called()
            provider.send_message_v2.assert_not_called()
            provider.transcribe_audio_bytes.assert_not_called()
            assert not (await db.execute(select(AIMessage))).scalars().all()
            assert (await routes.get_my_ai_chat(db=db, current_user=user)).chat is None
    asyncio.run(run())


@db_test
def test_attachment_owner_access_and_private_api_serialization(tmp_path, monkeypatch):
    import src.database.models.ai.attachment as storage
    monkeypatch.setattr(storage, "ATTACHMENTS_DIR", tmp_path)
    async def run():
        async with database() as (db, user):
            stranger = User(name="Other", surname="Member", password_hash="test")
            chat = AIChat(user_id=user.id, conversation_id="conv_private_test")
            db.add_all([chat, stranger]); await db.flush()
            message = AIMessage(user_id=user.id, chat_id=chat.id, text="private", sender=MessageSender.USER)
            db.add(message); await db.flush()
            attachment = Attachment(message_id=message.id, is_private=False, filename="file.txt", type=AttachmentType.DOCUMENT, mime_type="text/plain", size_bytes=7)
            db.add(attachment); await db.flush()
            attachment.path.parent.mkdir(parents=True)
            attachment.path.write_text("private")
            serialized = AIAttachmentRead.model_validate(attachment).model_dump(mode="json")
            assert serialized["is_private"] is True and serialized["download_path"].endswith(f"/{attachment.id}")
            async def session(): yield db
            app.dependency_overrides[get_db] = session
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://example.test") as client:
                    path = serialized["download_path"]
                    assert (await client.get(path)).status_code == 401
                    app.dependency_overrides[get_current_user] = lambda: stranger
                    assert (await client.get(path)).status_code == 404
                    app.dependency_overrides[get_current_user] = lambda: user
                    response = await client.get(path)
                    assert response.status_code == 200 and response.text == "private"
                    assert "no-store" in response.headers["cache-control"]
                    attachment.path.unlink()
                    assert (await client.get(path)).status_code == 404
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)
    asyncio.run(run())
