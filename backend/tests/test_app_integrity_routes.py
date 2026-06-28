from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import src.app.modules.app_integrity.router as app_integrity_router_module
import src.app.modules.auth.dependencies as auth_dependencies
import src.app.modules.users.me.ai_chat as ai_chat_router_module
import src.app.services.app_integrity.common as app_integrity_common
import src.app.services.app_integrity.service as app_integrity
from src.app.main import app
from src.database import get_db
from src.database.models import User
from src.integrations.ai import get_professor_client


def _fake_user() -> User:
    return User(
        id=123,
        username="integrity-user",
        email="integrity-user@example.com",
        password_hash="hash",
        name="Integrity",
        surname="User",
        is_active=True,
    )


def _integrity_headers(*, action: str, token: str = "dev-token") -> dict[str, str]:
    return {
        app_integrity.APP_INTEGRITY_ACTION_HEADER: action,
        app_integrity.APP_INTEGRITY_PLATFORM_HEADER: "ios",
        app_integrity.APP_INTEGRITY_REQUEST_HASH_HEADER: "test-request-hash",
        app_integrity.APP_INTEGRITY_TOKEN_HEADER: token,
    }


class _FakeDb:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        return None

    async def refresh(self, value):
        if getattr(value, "id", None) is None:
            value.id = 1


@pytest.fixture(autouse=True)
def enforce_app_integrity(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_integrity_common, "APP_INTEGRITY_MODE", "enforce")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_DEV_TOKEN", "dev-token")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_VERIFIER_URL", None)


@pytest.fixture()
def guarded_app_overrides():
    async def fake_get_db():
        yield _FakeDb()

    async def fake_get_current_user():
        return _fake_user()

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[auth_dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[get_professor_client] = lambda: SimpleNamespace()

    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(auth_dependencies.get_current_user, None)
        app.dependency_overrides.pop(get_professor_client, None)


def test_orders_route_rejects_missing_app_integrity(guarded_app_overrides):
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/users/me/orders",
            json={"draft_id": 1, "payment_method": "later"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "App integrity check failed"


def test_payments_route_rejects_missing_app_integrity(guarded_app_overrides):
    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/payments/create", json={"order_id": 1})

    assert response.status_code == 403
    assert response.json()["detail"] == "App integrity check failed"


def test_ai_chat_route_rejects_missing_app_integrity(guarded_app_overrides):
    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/users/me/ai-chat", data={"text": "hello"})

    assert response.status_code == 403
    assert response.json()["detail"] == "App integrity check failed"


def test_ai_chat_route_accepts_matching_app_integrity(monkeypatch: pytest.MonkeyPatch, guarded_app_overrides):
    async def fake_get_or_create_user_chat(*_args, **_kwargs):
        return {
            "id": 77,
            "user_id": 123,
            "conversation_id": "conv_123",
            "current_tokens": 10,
            "total_tokens": 42,
            "messages": [],
            "created_at": "2026-05-01T00:00:00Z",
            "updated_at": "2026-05-01T00:00:00Z",
        }

    monkeypatch.setattr(ai_chat_router_module, "get_or_create_user_chat", fake_get_or_create_user_chat)

    with TestClient(app) as test_client:
        response = test_client.get(
            "/api/v1/users/me/ai-chat",
            headers=_integrity_headers(action="ai-chat:read"),
        )

    assert response.status_code == 200, response.text
    assert response.json()["chat"]["id"] == 77


def test_ios_assertion_challenge_requires_action(guarded_app_overrides):
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/app-integrity/ios/challenge",
            json={"purpose": "assertion"},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "action is required for assertion challenges"


def test_ios_attestation_challenge_returns_one_time_challenge(monkeypatch: pytest.MonkeyPatch, guarded_app_overrides):
    monkeypatch.setattr(app_integrity.secrets, "token_urlsafe", lambda _length: "server-challenge")

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/app-integrity/ios/challenge",
            json={"purpose": "attestation"},
        )

    assert response.status_code == 200, response.text
    assert response.json() == {"challenge": "server-challenge"}


def test_ios_register_route_returns_registered_key(monkeypatch: pytest.MonkeyPatch, guarded_app_overrides):
    async def fake_register_ios_app_attest_key_service(*_args, **_kwargs):
        return SimpleNamespace(key_id="key-id", environment="production")

    monkeypatch.setattr(
        app_integrity_router_module,
        "register_ios_app_attest_key_service",
        fake_register_ios_app_attest_key_service,
    )

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/app-integrity/ios/register",
            json={
                "key_id": "key-id",
                "challenge": "server-challenge",
                "attestation_object": "attestation-object",
            },
        )

    assert response.status_code == 200, response.text
    assert response.json() == {"key_id": "key-id", "environment": "production"}
