from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import EMAIL_VERIFICATION_MAX_ATTEMPTS, ufa_now
from src.app.services.auth.service import login, password_reset
from src.app.services.security import hash_password
from src.database.models import EmailVerificationCode, User, UserPasswordReset
from src.integrations.website_identity import WebsiteIdentityError
from test_referrals_api import sync_engine

BASE = "/api/v1/auth/password-reset"
OLD = "old-test-password"
NEW = "new-test-password"


@pytest.fixture()
def mail(monkeypatch):
    codes = iter(["345678", "456789", "567890", "678901"])
    monkeypatch.setattr(password_reset, "generate_email_verification_code", lambda: next(codes))
    send = AsyncMock()
    monkeypatch.setattr(password_reset, "send_user_password_reset_code_email", send)
    return send


@pytest.fixture()
def account(register_verified_user):
    email = f"reset-{uuid4().hex}@example.com"
    return email, register_verified_user({"email": email, "password": OLD, "name": "Test", "surname": "Customer"})


def request_code(client, email):
    return client.post(f"{BASE}/request", json={"email": email})


def confirm(client, email, code, password=NEW):
    return client.post(f"{BASE}/confirm", json={"email": email, "code": code, "password": password})


def test_reset_invalidates_old_sessions_and_login_codes_and_blocks_site_password(client, account, mail, monkeypatch):
    email, account_data = account
    website = AsyncMock(side_effect=WebsiteIdentityError(
        status_code=401, code="invalid", message="Invalid", message_ru="Invalid", message_en="Invalid",
    ))
    monkeypatch.setattr(login, "website_identity_configured", lambda: True)
    monkeypatch.setattr(login, "WebsiteIdentityClient", lambda: SimpleNamespace(authenticate=website))
    login_path = "/api/v1/auth/login"
    assert client.post(login_path, json={"login": email, "password": OLD}).status_code == 200
    website.reset_mock()

    assert request_code(client, email.upper()).json() == {"ok": True}
    mail.assert_awaited_once_with(to_email=email, code="345678")
    assert client.post(f"{login_path}/verify", json={"email": email, "code": "345678"}).status_code == 400
    assert confirm(client, email, "345678").json() == {"ok": True}
    assert confirm(client, email, "345678").status_code == 400
    assert client.post(f"{login_path}/verify", json={"email": email, "code": "123456"}).status_code == 400
    headers = {"Authorization": f"Bearer {account_data['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    refresh = {key: account_data[key] for key in ("session_id", "refresh_token")}
    assert client.post("/api/v1/auth/refresh", json=refresh).status_code == 401
    assert client.post(login_path, json={"login": email, "password": OLD}).status_code == 401
    website.assert_not_awaited()
    # An alternate website username can resolve the same app account.
    website.side_effect = None
    website.return_value = {"user": {"login": "old-website-login", "email": email}}
    assert client.post(login_path, json={"login": "old-website-login", "password": OLD}).status_code == 401
    website.return_value = None
    website.side_effect = WebsiteIdentityError(
        status_code=401, code="invalid", message="Invalid", message_ru="Invalid", message_en="Invalid",
    )
    response = client.post(login_path, json={"login": email, "password": NEW})
    assert response.status_code == 200 and response.json()["verification_required"]


def test_resend_expiration_attempt_limit_and_password_change(client, account, mail):
    email, data = account
    uid = data["user"]["id"]
    assert request_code(client, email).status_code == 200
    assert request_code(client, email).status_code == 200
    for _ in range(EMAIL_VERIFICATION_MAX_ATTEMPTS):
        assert confirm(client, email, "345678").status_code == 400
    assert confirm(client, email, "456789").status_code == 400
    assert request_code(client, email).status_code == 200
    assert request_code(client, email).status_code == 429
    with Session(sync_engine) as db:
        pending = db.get(UserPasswordReset, uid)
        pending.expires_at = ufa_now() - timedelta(seconds=1)
        db.commit()
    assert confirm(client, email, "567890").status_code == 400
    with Session(sync_engine) as db:
        pending = db.get(UserPasswordReset, uid)
        pending.expires_at = ufa_now() + timedelta(minutes=5)
        db.get(User, uid).password_hash = hash_password("changed-separately")
        db.commit()
    assert confirm(client, email, "567890").status_code == 400


def test_reset_request_response_does_not_disclose_unknown_or_ineligible_email(client, account, mail):
    email, data = account
    missing = f"missing-{uuid4().hex}@example.com"
    assert request_code(client, missing).json() == {"ok": True}
    with Session(sync_engine) as db:
        db.get(User, data["user"]["id"]).is_active = False
        db.commit()
    assert request_code(client, email).json() == {"ok": True}
    assert confirm(client, email, "345678").status_code == 400
    mail.assert_not_awaited()


@pytest.mark.anyio
async def test_customer_recovery_exchanges_the_code_for_a_single_use_token(monkeypatch):
    email = "customer@example.com"
    user = SimpleNamespace(id=42, is_active=True, is_verified=True, password_hash=hash_password(OLD))
    pending = UserPasswordReset(
        user_id=user.id, email=email, password_fingerprint=password_reset._password_fingerprint(user),
        code_hash=password_reset.hash_email_verification_code("345678"),
        expires_at=ufa_now() + timedelta(minutes=5), attempt_count=0,
    )
    db = SimpleNamespace(get=AsyncMock(return_value=pending), execute=AsyncMock(), commit=AsyncMock())

    async def delete(record):
        assert record is pending
        db.get.return_value = None

    db.delete = delete
    ios = SimpleNamespace(headers={"x-app-platform": "ios"})
    android = SimpleNamespace(headers={"x-app-platform": "android"})
    monkeypatch.setattr(password_reset, "enforce_rate_limit", AsyncMock())
    monkeypatch.setattr(password_reset, "_active_verified_user", AsyncMock(return_value=user))
    with pytest.raises(HTTPException, match="Invalid or expired verification code"):
        await password_reset.verify_password_reset(db, ios, email=email, code="345679")
    assert pending.attempt_count == 1
    token = await password_reset.verify_password_reset(db, ios, email=email, code="345678")
    assert token not in pending.code_hash
    assert password_reset._password_fingerprint(user) == pending.password_fingerprint

    with pytest.raises(HTTPException, match="Invalid or expired verification code"):
        await password_reset.confirm_password_reset(db, ios, email=email, code="345678", password=NEW)
    with pytest.raises(HTTPException, match="Invalid or expired verification code"):
        await password_reset.confirm_password_reset(db, android, email=email, reset_token="wrong-token", password=NEW)
    await password_reset.confirm_password_reset(db, ios, email=email, reset_token=token, password=NEW)
    assert user.app_password_reset_at is not None
    assert password_reset._password_fingerprint(user) != pending.password_fingerprint
    with pytest.raises(HTTPException, match="Invalid or expired verification code"):
        await password_reset.confirm_password_reset(db, ios, email=email, reset_token=token, password=NEW)
