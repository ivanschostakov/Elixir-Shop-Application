from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import src.app.modules.auth.dependencies as auth_dependencies
import src.app.modules.users.me.ai_chat as ai_chat_router_module
import src.app.services.ai_chat as ai_chat_service
from src.app.main import app
from src.database import get_db
from src.database.models import User
from src.integrations.ai.enums import AttachmentType, BotModel
from src.integrations.ai import get_professor_client
from src.app.services.ai_chat import _attachment_storage_filename, _load_uploads, resolve_user_bot_model


def _fake_user() -> User:
    return User(
        id=123,
        username="chat-user",
        email="chat-user@example.com",
        password_hash="hash",
        name="Chat",
        surname="User",
        is_active=True,
    )


def _chat_payload() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": 77,
        "user_id": 123,
        "conversation_id": "conv_123",
        "current_tokens": 10,
        "total_tokens": 42,
        "messages": [
            {
                "id": 1,
                "user_id": 123,
                "chat_id": 77,
                "text": "hello",
                "sender": "user",
                "bot_model": "free",
                "tokens": 10,
                "attachments": [],
                "created_at": now,
                "updated_at": now,
            }
        ],
        "created_at": now,
        "updated_at": now,
    }


def test_get_my_ai_chat_bootstraps_when_missing(monkeypatch):
    async def fake_get_db():
        yield object()

    async def fake_get_current_user():
        return _fake_user()

    async def fake_get_or_create_user_chat(*args, **kwargs):
        return _chat_payload()

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[auth_dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[get_professor_client] = lambda: SimpleNamespace()
    monkeypatch.setattr(ai_chat_router_module, "get_or_create_user_chat", fake_get_or_create_user_chat)

    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/users/me/ai-chat")

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["chat"]["id"] == 77
        assert payload["chat"]["conversation_id"] == "conv_123"
        assert payload["chat"]["current_tokens"] == 10
        assert payload["chat"]["total_tokens"] == 42
        assert payload["last_turn"] is None
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(auth_dependencies.get_current_user, None)
        app.dependency_overrides.pop(get_professor_client, None)


def test_post_my_ai_chat_message_returns_turn_meta(monkeypatch):
    async def fake_get_db():
        yield object()

    async def fake_get_current_user():
        return _fake_user()

    async def fake_send_user_chat_message(*args, **kwargs):
        attachments = kwargs.get("attachments")
        assert attachments is not None and len(attachments) == 1
        return _chat_payload(), {
            "selected_bot_model": "premium",
            "input_tokens": 101,
            "cached_input_tokens": 11,
            "output_tokens": 55,
            "conversation_reset_reason": "soft_input_limit_post_response",
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[auth_dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[get_professor_client] = lambda: SimpleNamespace()
    monkeypatch.setattr(ai_chat_router_module, "send_user_chat_message", fake_send_user_chat_message)

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/users/me/ai-chat",
                data={"text": "hello"},
                files=[("attachments", ("a.txt", b"abc", "text/plain"))],
            )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["chat"]["id"] == 77
        assert payload["last_turn"]["selected_bot_model"] == "premium"
        assert payload["last_turn"]["input_tokens"] == 101
        assert payload["last_turn"]["cached_input_tokens"] == 11
        assert payload["last_turn"]["output_tokens"] == 55
        assert payload["last_turn"]["conversation_reset_reason"] == "soft_input_limit_post_response"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(auth_dependencies.get_current_user, None)
        app.dependency_overrides.pop(get_professor_client, None)


def test_post_my_ai_chat_message_rejects_blank_text(monkeypatch):
    async def fake_get_db():
        yield object()

    async def fake_get_current_user():
        return _fake_user()

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[auth_dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[get_professor_client] = lambda: SimpleNamespace()

    try:
        with TestClient(app) as test_client:
            response = test_client.post("/api/v1/users/me/ai-chat", data={"text": "   "})

        assert response.status_code == 422, response.text
        assert response.json()["detail"] == "text must not be empty"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(auth_dependencies.get_current_user, None)
        app.dependency_overrides.pop(get_professor_client, None)


def test_post_my_ai_chat_transcribe_returns_whisper_text():
    async def fake_get_current_user():
        return _fake_user()

    class FakeProfessorClient:
        async def transcribe_audio_bytes(self, *, filename: str, content: bytes) -> str:
            assert filename == "voice.m4a"
            assert content == b"audio"
            return "Привет"

    app.dependency_overrides[auth_dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[get_professor_client] = lambda: FakeProfessorClient()

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/users/me/ai-chat/transcribe",
                files={"audio": ("voice.m4a", b"audio", "audio/m4a")},
            )

        assert response.status_code == 200, response.text
        assert response.json() == {"text": "Привет"}
    finally:
        app.dependency_overrides.pop(auth_dependencies.get_current_user, None)
        app.dependency_overrides.pop(get_professor_client, None)


def test_post_my_ai_chat_transcribe_rejects_empty_audio():
    async def fake_get_current_user():
        return _fake_user()

    class FakeProfessorClient:
        async def transcribe_audio_bytes(self, *, filename: str, content: bytes) -> str:
            raise AssertionError("empty audio should be rejected before transcription")

    app.dependency_overrides[auth_dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[get_professor_client] = lambda: FakeProfessorClient()

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/users/me/ai-chat/transcribe",
                files={"audio": ("voice.m4a", b"", "audio/m4a")},
            )

        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "audio must not be empty"
    finally:
        app.dependency_overrides.pop(auth_dependencies.get_current_user, None)
        app.dependency_overrides.pop(get_professor_client, None)


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _FakeAsyncSession:
    def __init__(self, value):
        self.value = value
        self.last_stmt = None

    async def execute(self, stmt):
        self.last_stmt = stmt
        return _FakeScalarResult(self.value)


class _FakeUploadFile:
    def __init__(self, filename: str, content_type: str, payload: bytes = b"payload"):
        self.filename = filename
        self.content_type = content_type
        self._payload = payload

    async def read(self):
        return self._payload


def test_load_uploads_preserves_original_filename_but_normalizes_ai_image_extension():
    uploads = [_FakeUploadFile("PHOTO.JPG", "image/jpeg")]

    loaded = asyncio.run(_load_uploads(uploads))

    assert loaded[0].filename == "PHOTO.JPG"
    assert loaded[0].ai_filename == "PHOTO.jpg"


def test_load_uploads_adds_supported_ai_image_extension_from_mime_type():
    uploads = [_FakeUploadFile("photo", "image/png")]

    loaded = asyncio.run(_load_uploads(uploads))

    assert loaded[0].filename == "photo"
    assert loaded[0].ai_filename == "photo.png"


def test_load_uploads_converts_heic_for_ai_payload(monkeypatch):
    monkeypatch.setattr(ai_chat_service, "_convert_image_to_jpeg", lambda content: b"jpeg-content")
    uploads = [_FakeUploadFile("IMG_1234.HEIC", "image/heic", b"heic-content")]

    loaded = asyncio.run(_load_uploads(uploads))

    assert loaded[0].filename == "IMG_1234.HEIC"
    assert loaded[0].content == b"heic-content"
    assert loaded[0].ai_filename == "IMG_1234.jpg"
    assert loaded[0].ai_content == b"jpeg-content"
    assert loaded[0].kind == AttachmentType.IMAGE


def test_load_uploads_treats_heic_extension_as_image_when_mime_is_generic(monkeypatch):
    monkeypatch.setattr(ai_chat_service, "_convert_image_to_jpeg", lambda content: b"jpeg-content")
    uploads = [_FakeUploadFile("IMG_1234.heic", "application/octet-stream", b"heic-content")]

    loaded = asyncio.run(_load_uploads(uploads))

    assert loaded[0].ai_filename == "IMG_1234.jpg"
    assert loaded[0].ai_content == b"jpeg-content"
    assert loaded[0].kind == AttachmentType.IMAGE


def test_load_uploads_rejects_unsupported_image_format():
    uploads = [_FakeUploadFile("scan.tiff", "image/tiff")]

    with pytest.raises(Exception) as exc_info:
        asyncio.run(_load_uploads(uploads))

    assert getattr(exc_info.value, "status_code", None) == 400
    assert "Unsupported image format" in str(getattr(exc_info.value, "detail", ""))


def test_attachment_storage_filename_preserves_safe_extension():
    filename = _attachment_storage_filename("PHOTO.JPG", "image/jpeg")

    assert filename.endswith(".jpg")
    assert filename != "PHOTO.JPG"


def test_attachment_storage_filename_uses_mime_extension_when_filename_has_none():
    filename = _attachment_storage_filename("photo", "image/png")

    assert filename.endswith(".png")


def test_resolve_user_bot_model_thresholds():
    session_free = _FakeAsyncSession(5000)
    model_free = asyncio.run(resolve_user_bot_model(session_free, user_id=1))
    assert model_free == BotModel.FREE

    session_premium = _FakeAsyncSession(5000.01)
    model_premium = asyncio.run(resolve_user_bot_model(session_premium, user_id=1))
    assert model_premium == BotModel.PREMIUM


def test_resolve_user_bot_model_query_filters():
    session = _FakeAsyncSession(0)
    asyncio.run(resolve_user_bot_model(session, user_id=7))
    compiled = str(session.last_stmt)
    assert "orders.is_paid" in compiled
    assert "orders.is_canceled" in compiled
    assert "orders.payment_paid_at" in compiled
    assert "coalesce(orders.payment_status" in compiled


def test_send_user_chat_message_triggers_ai_reply_notification(monkeypatch: pytest.MonkeyPatch):
    class _FakeDb:
        async def commit(self):
            return None

        async def rollback(self):
            return None

    class _FakeProfessorClient:
        async def send_message_v2(self, **_kwargs):
            return {
                "text": "AI reply",
                "conversation_id": "conv_999",
                "input_tokens": 12,
                "cached_input_tokens": 0,
                "output_tokens": 7,
                "files": [],
                "conversation_reset_reason": None,
            }

    chat = SimpleNamespace(id=77, conversation_id="conv_123", current_tokens=0, total_tokens=3)
    user_message = SimpleNamespace(id=101)
    ai_message = SimpleNamespace(id=202)
    refreshed_chat = SimpleNamespace(id=77)
    message_counter = {"value": 0}
    captured_notification: dict[str, int] = {}

    async def fake_get_or_create_user_chat(*args, **kwargs):
        return chat

    async def fake_resolve_user_bot_model(*args, **kwargs):
        return BotModel.FREE

    async def fake_create_ai_message(*args, **kwargs):
        message_counter["value"] += 1
        return user_message if message_counter["value"] == 1 else ai_message

    async def fake_update_ai_message(*args, **kwargs):
        return None

    async def fake_update_ai_chat(*args, **kwargs):
        return None

    async def fake_get_ai_chat_by_id(*args, **kwargs):
        return refreshed_chat

    async def fake_send_ai_reply_notification(_db, *, user_id: int, chat_id: int, message_id: int):
        captured_notification["user_id"] = user_id
        captured_notification["chat_id"] = chat_id
        captured_notification["message_id"] = message_id

    monkeypatch.setattr(ai_chat_service, "get_or_create_user_chat", fake_get_or_create_user_chat)
    monkeypatch.setattr(ai_chat_service, "resolve_user_bot_model", fake_resolve_user_bot_model)
    monkeypatch.setattr(ai_chat_service, "create_ai_message", fake_create_ai_message)
    monkeypatch.setattr(ai_chat_service, "update_ai_message", fake_update_ai_message)
    monkeypatch.setattr(ai_chat_service, "update_ai_chat", fake_update_ai_chat)
    monkeypatch.setattr(ai_chat_service, "get_ai_chat_by_id", fake_get_ai_chat_by_id)
    monkeypatch.setattr(ai_chat_service, "send_ai_reply_notification", fake_send_ai_reply_notification)

    result_chat, turn_meta = asyncio.run(
        ai_chat_service.send_user_chat_message(
            _FakeDb(),
            user=_fake_user(),
            text="hello",
            attachments=None,
            professor_client=_FakeProfessorClient(),
        )
    )

    assert result_chat is refreshed_chat
    assert turn_meta["output_tokens"] == 7
    assert captured_notification == {
        "user_id": 123,
        "chat_id": 77,
        "message_id": 202,
    }


def test_send_user_chat_message_keeps_user_message_when_ai_call_fails(monkeypatch: pytest.MonkeyPatch):
    class _FakeDb:
        def __init__(self):
            self.commit_calls = 0
            self.rollback_calls = 0

        async def commit(self):
            self.commit_calls += 1

        async def rollback(self):
            self.rollback_calls += 1

    class _FailingProfessorClient:
        async def send_message_v2(self, **_kwargs):
            raise RuntimeError("ai provider unavailable")

    chat = SimpleNamespace(id=77, conversation_id="conv_123", current_tokens=0, total_tokens=3)
    user_message = SimpleNamespace(id=101)
    message_counter = {"value": 0}

    async def fake_get_or_create_user_chat(*args, **kwargs):
        return chat

    async def fake_resolve_user_bot_model(*args, **kwargs):
        return BotModel.FREE

    async def fake_create_ai_message(*args, **kwargs):
        message_counter["value"] += 1
        return user_message

    monkeypatch.setattr(ai_chat_service, "get_or_create_user_chat", fake_get_or_create_user_chat)
    monkeypatch.setattr(ai_chat_service, "resolve_user_bot_model", fake_resolve_user_bot_model)
    monkeypatch.setattr(ai_chat_service, "create_ai_message", fake_create_ai_message)

    db = _FakeDb()
    with pytest.raises(RuntimeError, match="ai provider unavailable"):
        asyncio.run(
            ai_chat_service.send_user_chat_message(
                db,
                user=_fake_user(),
                text="hello",
                attachments=None,
                professor_client=_FailingProfessorClient(),
            )
        )

    assert message_counter["value"] == 1
    assert db.commit_calls == 1
    assert db.rollback_calls == 1
