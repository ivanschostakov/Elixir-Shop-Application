from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

import src.app.modules.auth.dependencies as auth_dependencies
import src.app.modules.products.router as products_router_module
from src.app.main import app
from src.app.modules.admin.orders import ALLOWED_TRANSITIONS
from src.app.services.admin.security import (
    create_admin_access_token,
    decode_admin_token,
    decrypt_totp_secret,
    encrypt_totp_secret,
    verify_totp,
)
from src.app.services.security import create_access_token
from src.database import get_db


def test_totp_matches_rfc_vector_and_rejects_invalid_code():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert verify_totp(secret, "287082", timestamp=59, window=0)
    assert not verify_totp(secret, "287083", timestamp=59, window=0)
    assert not verify_totp(secret, "not-a-code", timestamp=59, window=0)


def test_admin_access_token_has_isolated_audience_and_type():
    token = create_admin_access_token(user_id=42, session_id=7)
    payload = decode_admin_token(token, expected_type="admin_access")
    assert payload is not None
    assert payload["aud"] == "admin"
    assert payload["sub"] == "42"
    assert payload["sid"] == "7"
    assert decode_admin_token(token, expected_type="admin_challenge") is None


def test_totp_secret_encryption_round_trip():
    secret = "JBSWY3DPEHPK3PXP"
    encrypted = encrypt_totp_secret(secret)
    assert encrypted != secret
    assert decrypt_totp_secret(encrypted) == secret
    assert decrypt_totp_secret("invalid") is None


def test_order_transitions_are_explicit_and_terminal():
    assert "paid" in ALLOWED_TRANSITIONS["invoice_sent"]
    assert "delivered" in ALLOWED_TRANSITIONS["sent"]
    assert ALLOWED_TRANSITIONS["canceled"] == frozenset()


def test_admin_endpoint_requires_admin_bearer_token(client: TestClient):
    response = client.get("/api/v1/admin/dashboard")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_mobile_access_token_cannot_use_admin_session(monkeypatch: pytest.MonkeyPatch):
    async def fake_get_session(*args, **kwargs):
        return SimpleNamespace(
            id=7,
            user_id=42,
            purpose="admin",
            revoked_at=None,
            expires_at=datetime(2100, 1, 1, tzinfo=timezone.utc),
        )

    monkeypatch.setattr(auth_dependencies, "get_user_session_by_id", fake_get_session)
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_access_token(user_id=42, session_id=7),
    )
    with pytest.raises(HTTPException) as error:
        await auth_dependencies.get_current_user(credentials=credentials, db=object())
    assert error.value.status_code == 401


def test_guest_can_submit_review_for_moderation(monkeypatch: pytest.MonkeyPatch):
    now = datetime.now(timezone.utc)

    class FakeDb:
        async def commit(self):
            return None

        async def rollback(self):
            return None

    async def fake_get_db():
        yield FakeDb()

    async def fake_get_product_by_id(*args, **kwargs):
        return object()

    async def fake_create_product_review(*args, user_id, product_id, data, **kwargs):
        assert user_id is None
        assert product_id == 91
        assert data.guest_name == "Гость"
        return type("CreatedReview", (), {"id": 501})()

    async def fake_get_review_by_id(*args, **kwargs):
        return object()

    async def fake_rate_limit(*args, **kwargs):
        return None

    async def fake_bump_review_cache_namespaces():
        return None

    def fake_serialize_review(*args, **kwargs):
        return {
            "id": 501,
            "author_username": "Гость",
            "product_id": 91,
            "value": 5,
            "text": "Отличный товар",
            "answer": None,
            "attachments": [],
            "likes": 0,
            "dislikes": 0,
            "moderated": False,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(products_router_module, "get_product_by_id", fake_get_product_by_id)
    monkeypatch.setattr(products_router_module, "create_product_review", fake_create_product_review)
    monkeypatch.setattr(products_router_module, "get_review_by_id", fake_get_review_by_id)
    monkeypatch.setattr(products_router_module, "enforce_rate_limit", fake_rate_limit)
    monkeypatch.setattr(products_router_module, "_bump_review_cache_namespaces", fake_bump_review_cache_namespaces)
    monkeypatch.setattr(products_router_module, "serialize_review", fake_serialize_review)

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/products/91/reviews",
                data={"value": "5", "text": "Отличный товар"},
            )
        assert response.status_code == 201, response.text
        assert response.json()["moderated"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)
