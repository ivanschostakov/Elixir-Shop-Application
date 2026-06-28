from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.app.modules.auth.schemas.phone import PhoneAuthRegisterPayload, PhoneAuthStartPayload
from src.app.services.auth.service import login_user_by_phone, register_user_by_phone, start_phone_auth


class _DummyDbSession:
    def __init__(self):
        self.committed = False
        self.refreshed_user = None
        self.rolled_back = False

    async def commit(self):
        self.committed = True

    async def refresh(self, user):
        self.refreshed_user = user

    async def rollback(self):
        self.rolled_back = True


def test_phone_auth_start_payload_normalizes_phone():
    payload = PhoneAuthStartPayload(phone_number=" +7 (999) 000-11-22 ")

    assert payload.phone_number == "+79990001122"


def test_phone_auth_register_payload_allows_missing_email():
    payload = PhoneAuthRegisterPayload(
        phone_number=" +7 (999) 000-11-22 ",
        name=" Phone ",
        surname=" User ",
        password="supersecret",
    )

    assert payload.phone_number == "+79990001122"
    assert payload.name == "Phone"
    assert payload.surname == "User"
    assert payload.email is None


@pytest.mark.anyio
async def test_register_user_by_phone_without_email_creates_verified_user_and_returns_tokens(monkeypatch: pytest.MonkeyPatch):
    payload = PhoneAuthRegisterPayload(
        phone_number="+79990001122",
        name="Phone",
        surname="User",
        email=None,
        password="supersecret",
    )
    db = _DummyDbSession()
    request = object()
    created_user = SimpleNamespace(
        id=17,
        email=None,
        phone_number=payload.phone_number,
        is_verified=True,
    )
    captured: dict[str, object] = {}

    async def fake_apply_auth_rate_limit(request_arg, *, scope: str, principal: str | None = None, verify: bool = False):
        captured["rate_limit"] = {
            "request": request_arg,
            "scope": scope,
            "principal": principal,
            "verify": verify,
        }

    async def fake_get_user_by_phone_number(*_args, **_kwargs):
        return None

    async def fake_get_counterparty_for_phone(*_args, **_kwargs):
        return None

    def fake_hash_password(password: str) -> str:
        captured["password"] = password
        return "hashed-password"

    async def fake_create_user(db_arg, user_create, commit: bool = False):
        captured["db"] = db_arg
        captured["user_create"] = user_create
        captured["commit"] = commit
        return created_user

    async def fake_build_auth_tokens_response(user_arg, db_arg):
        assert user_arg is created_user
        assert db_arg is db
        return "tokens"

    monkeypatch.setattr("src.app.services.auth.service._apply_auth_rate_limit", fake_apply_auth_rate_limit)
    monkeypatch.setattr("src.app.services.auth.service.get_user_by_phone_number", fake_get_user_by_phone_number)
    monkeypatch.setattr("src.app.services.auth.service._get_counterparty_for_phone", fake_get_counterparty_for_phone)
    monkeypatch.setattr("src.app.services.auth.service.hash_password", fake_hash_password)
    monkeypatch.setattr("src.app.services.auth.service.create_user", fake_create_user)
    monkeypatch.setattr("src.app.services.auth.service._build_auth_tokens_response", fake_build_auth_tokens_response)

    response = await register_user_by_phone(request, payload, db, SimpleNamespace())

    user_create = captured["user_create"]
    assert captured["rate_limit"] == {
        "request": request,
        "scope": "auth:phone_register",
        "principal": payload.phone_number,
        "verify": False,
    }
    assert captured["password"] == payload.password
    assert captured["db"] is db
    assert captured["commit"] is False
    assert user_create.phone_number == payload.phone_number
    assert user_create.email is None
    assert user_create.is_verified is True
    assert db.committed is True
    assert db.refreshed_user is created_user
    assert response == "tokens"


@pytest.mark.anyio
async def test_start_phone_auth_returns_claim_step_for_counterparty_without_local_user(monkeypatch: pytest.MonkeyPatch):
    payload = PhoneAuthStartPayload(phone_number="+79990001122")

    async def fake_apply_auth_rate_limit(*_args, **_kwargs):
        return None

    async def fake_resolve_user_for_phone(*_args, **_kwargs):
        return None, {"id": str(uuid4()), "email": "counterparty@example.com"}

    monkeypatch.setattr("src.app.services.auth.service._apply_auth_rate_limit", fake_apply_auth_rate_limit)
    monkeypatch.setattr("src.app.services.auth.service._resolve_user_for_phone", fake_resolve_user_for_phone)

    response = await start_phone_auth(object(), payload, object(), SimpleNamespace())

    assert response.next_step == "claim"
    assert response.email_required is False
    assert response.email_hint == "co**********@example.com"


@pytest.mark.anyio
async def test_login_user_by_phone_updates_phone_identity_from_counterparty(monkeypatch: pytest.MonkeyPatch):
    payload = SimpleNamespace(phone_number="+79990001122", password="supersecret")
    db = _DummyDbSession()
    user = SimpleNamespace(
        id=17,
        is_active=True,
        password_hash="hashed-password",
        phone_number=None,
        moysklad_counterparty_id=None,
    )
    counterparty_id = uuid4()

    async def fake_apply_auth_rate_limit(*_args, **_kwargs):
        return None

    async def fake_resolve_user_for_phone(*_args, **_kwargs):
        return user, {"id": str(counterparty_id), "email": "counterparty@example.com"}

    async def fake_build_auth_tokens_response(user_arg, db_arg):
        assert user_arg is user
        assert db_arg is db
        return "tokens"

    monkeypatch.setattr("src.app.services.auth.service._apply_auth_rate_limit", fake_apply_auth_rate_limit)
    monkeypatch.setattr("src.app.services.auth.service._resolve_user_for_phone", fake_resolve_user_for_phone)
    monkeypatch.setattr("src.app.services.auth.service.verify_password", lambda provided, stored: provided == payload.password and stored == user.password_hash)
    monkeypatch.setattr("src.app.services.auth.service._build_auth_tokens_response", fake_build_auth_tokens_response)

    response = await login_user_by_phone(object(), payload, db, SimpleNamespace())

    assert response == "tokens"
    assert user.phone_number == payload.phone_number
    assert user.moysklad_counterparty_id == counterparty_id
    assert db.committed is True
    assert db.refreshed_user is user
