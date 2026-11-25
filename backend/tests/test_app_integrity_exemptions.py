from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import src.app.modules.app_integrity.router as integrity_router
import src.app.modules.users.me.ai_chat as chat_router
import src.app.services.app_integrity.service as integrity
from src.app.main import app
from src.app.modules.auth.dependencies import get_current_user
from src.database import get_db
from src.database.models import User

pytestmark = pytest.mark.real_app_integrity


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _user(user_id=17, *, active=True):
    return User(id=user_id, username="urusy001", email="integrity@example.test", is_active=active)


@pytest.fixture
def exempt_account(monkeypatch):
    user = _user()
    monkeypatch.setattr(integrity, "APP_INTEGRITY_EXEMPT_USER_IDS", frozenset({"17"}))
    monkeypatch.setattr(integrity, "APP_INTEGRITY_VERIFIER_URL", None)
    monkeypatch.setattr(chat_router, "get_ai_chat_by_user_id", AsyncMock(return_value=None))

    async def fake_user():
        return user

    async def fake_db():
        yield object()

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db
    return user


def test_exempt_authenticated_account_can_read_without_proof(exempt_account):
    with TestClient(app) as client:
        response = client.get("/api/v1/users/me/ai-chat")
    assert response.status_code == 200, response.text
    assert response.json()["chat"] is None
    chat_router.get_ai_chat_by_user_id.assert_awaited_once()
    assert chat_router.get_ai_chat_by_user_id.call_args.args[1] == 17


@pytest.mark.parametrize("user_id", [18, 78])
def test_other_authenticated_ids_stay_protected(exempt_account, user_id):
    exempt_account.id = user_id
    with TestClient(app) as client:
        response = client.get("/api/v1/users/me/ai-chat?user_id=17", headers={
            "x-user-id": "17", "x-app-integrity-exempt-user-id": "17",
            "x-app-integrity-token": "ios-grant:exempt:forged",
            "x-app-integrity-platform": "ios", "x-app-integrity-action": "ai-chat:read",
            "x-app-integrity-request-hash": "exempt:forged",
        })
    assert response.status_code == 403, response.text
    chat_router.get_ai_chat_by_user_id.assert_not_awaited()


def test_empty_allowlist_restores_verification(monkeypatch, exempt_account):
    monkeypatch.setattr(integrity, "APP_INTEGRITY_EXEMPT_USER_IDS", frozenset())
    with TestClient(app) as client:
        response = client.get("/api/v1/users/me/ai-chat")
    assert response.status_code == 403


@pytest.mark.parametrize("user", [None, _user(active=False), _user(18), _user("17,18")])
def test_exception_requires_exact_active_authenticated_user_id(monkeypatch, user):
    monkeypatch.setattr(integrity, "APP_INTEGRITY_EXEMPT_USER_IDS", frozenset({"17"}))
    assert integrity.app_integrity_exempt_for_user(user) is False


@pytest.mark.anyio
@pytest.mark.parametrize("action", ["orders:create", "payments:create", "ai-chat:read", "ai-companion"])
async def test_exempt_account_skips_device_verifiers(monkeypatch, exempt_account, action):
    ios = AsyncMock(side_effect=AssertionError("must not verify exempt account"))
    android = AsyncMock(side_effect=AssertionError("must not verify exempt account"))
    monkeypatch.setattr(integrity, "_verify_ios_app_attest_assertion", ios)
    monkeypatch.setattr(integrity, "_verify_android_play_integrity", android)
    await integrity.verify_app_integrity_request(
        Request({"type": "http", "headers": []}), action=action, current_user=exempt_account,
    )
    ios.assert_not_awaited()
    android.assert_not_awaited()


@pytest.mark.parametrize("route,payload", [
    ("register", {"key_id": "key", "challenge": "challenge", "attestation_object": "object"}),
    ("verify", {"key_id": "key", "challenge": "challenge", "assertion": "assertion", "action": "ai-chat:read"}),
])
def test_ios_handshake_exemption_does_not_persist_fake_keys_or_grants(monkeypatch, exempt_account, route, payload):
    register = AsyncMock(side_effect=AssertionError("must not register fake key"))
    verify = AsyncMock(side_effect=AssertionError("must not persist fake grant"))
    monkeypatch.setattr(integrity_router, "register_ios_app_attest_key_service", register)
    monkeypatch.setattr(integrity_router, "preverify_ios_app_attest_assertion", verify)
    with TestClient(app) as client:
        response = client.post(f"/api/v1/app-integrity/ios/{route}", json=payload)
    assert response.status_code == 200, response.text
    if route == "register":
        assert response.json() == {"key_id": "key", "environment": "exempt"}
    else:
        assert response.json()["grant"].startswith("exempt:")
    register.assert_not_awaited()
    verify.assert_not_awaited()


@pytest.mark.parametrize("route,service,payload", [
    ("register", "register_ios_app_attest_key_service", {"key_id": "key", "challenge": "challenge", "attestation_object": "object"}),
    ("verify", "preverify_ios_app_attest_assertion", {"key_id": "key", "challenge": "challenge", "assertion": "assertion", "action": "ai-chat:read"}),
])
def test_other_accounts_still_use_ios_verifier(monkeypatch, exempt_account, route, service, payload):
    exempt_account.id = 78
    verifier = AsyncMock(side_effect=HTTPException(403, "invalid proof"))
    monkeypatch.setattr(integrity_router, service, verifier)
    with TestClient(app) as client:
        response = client.post(f"/api/v1/app-integrity/ios/{route}", json=payload)
    assert response.status_code == 403
    verifier.assert_awaited_once()
    assert verifier.call_args.kwargs["user_id"] == 78


def test_exemption_does_not_remove_authentication(exempt_account):
    app.dependency_overrides.pop(get_current_user)
    with TestClient(app) as client:
        assert client.get("/api/v1/users/me/ai-chat").status_code == 401
        assert client.post("/api/v1/app-integrity/ios/register", json={
            "key_id": "key", "challenge": "challenge", "attestation_object": "object",
        }).status_code == 401
        assert client.post("/api/v1/app-integrity/ios/verify", json={
            "key_id": "key", "challenge": "challenge", "assertion": "assertion", "action": "ai-chat:read",
        }).status_code == 401


def test_public_config_does_not_disclose_exception(monkeypatch, exempt_account):
    monkeypatch.setattr(integrity_router, "APP_INTEGRITY_ANDROID_CLOUD_PROJECT_NUMBER", "123")
    with TestClient(app) as client:
        response = client.get("/api/v1/app-integrity/config")
    assert response.status_code == 200
    assert response.json() == {"android_cloud_project_number": "123"}
