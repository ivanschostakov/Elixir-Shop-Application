from types import SimpleNamespace
from uuid import uuid4
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from src.app.modules.auth.schemas.phone import PhoneAuthRegisterPayload, PhoneAuthStartPayload
from src.app.modules.auth.schemas.telegram import TelegramAuthPayload
from src.app.services.auth.service import (
    link_telegram_contact_to_user,
    login_user_by_phone,
    login_user_by_telegram,
    register_user_by_phone,
    start_phone_auth,
)


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


def _signed_telegram_init_data(bot_token: str, user: dict) -> str:
    values = {
        "auth_date": str(int(time.time())),
        "query_id": "AAE-test",
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode(values)


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


@pytest.mark.anyio
async def test_telegram_session_requires_contact_before_phone_is_linked(monkeypatch: pytest.MonkeyPatch):
    bot_token = "123456:test-token"
    init_data = _signed_telegram_init_data(
        bot_token,
        {"id": 901, "first_name": "Telegram", "last_name": "Buyer", "username": "buyer"},
    )

    async def fake_apply_auth_rate_limit(*_args, **_kwargs):
        return None

    async def fake_get_user_by_telegram_user_id(*_args, **_kwargs):
        return None

    monkeypatch.setattr("src.app.services.auth.service.TELEGRAM_BOT_TOKEN", bot_token)
    monkeypatch.setattr("src.app.services.auth.service._apply_auth_rate_limit", fake_apply_auth_rate_limit)
    monkeypatch.setattr("src.app.services.auth.service.get_user_by_telegram_user_id", fake_get_user_by_telegram_user_id)

    response = await login_user_by_telegram(object(), TelegramAuthPayload(init_data=init_data), object())

    assert response.contact_required is True
    assert response.telegram_user_id == 901


@pytest.mark.anyio
async def test_link_telegram_contact_to_user_creates_verified_phone_user(monkeypatch: pytest.MonkeyPatch):
    db = _DummyDbSession()
    captured: dict[str, object] = {}
    created_user = SimpleNamespace(id=44)

    async def fake_get_user_by_telegram_user_id(*_args, **_kwargs):
        return None

    async def fake_get_user_by_phone_number(*_args, **_kwargs):
        return None

    async def fake_create_user(db_arg, user_create, commit: bool = False):
        captured["db"] = db_arg
        captured["user_create"] = user_create
        captured["commit"] = commit
        return created_user

    monkeypatch.setattr("src.app.services.auth.service.get_user_by_telegram_user_id", fake_get_user_by_telegram_user_id)
    monkeypatch.setattr("src.app.services.auth.service.get_user_by_phone_number", fake_get_user_by_phone_number)
    monkeypatch.setattr("src.app.services.auth.service.create_user", fake_create_user)
    monkeypatch.setattr("src.app.services.auth.service.hash_password", lambda _password: "hashed-random-password")

    user, reason = await link_telegram_contact_to_user(
        db,
        telegram_user_id=901,
        phone_number="79990001122",
        first_name="Telegram",
        last_name="Buyer",
        username="buyer",
    )

    user_create = captured["user_create"]
    assert user is created_user
    assert reason is None
    assert captured["db"] is db
    assert captured["commit"] is False
    assert user_create.phone_number == "+79990001122"
    assert user_create.password_hash == "hashed-random-password"
    assert user_create.is_verified is True
    assert user_create.moysklad_counterparty_id is None
    assert user_create.telegram_user_id == 901
    assert user_create.telegram_username == "buyer"
    assert user_create.telegram_phone_confirmed_at is not None
    assert db.committed is True
    assert db.refreshed_user is created_user


@pytest.mark.anyio
async def test_link_telegram_contact_to_user_saves_moysklad_counterparty_id(monkeypatch: pytest.MonkeyPatch):
    db = _DummyDbSession()
    counterparty_id = uuid4()
    captured: dict[str, object] = {}
    created_user = SimpleNamespace(id=45, moysklad_counterparty_id=counterparty_id)

    class FakeMoySkladClient:
        def is_configured(self) -> bool:
            return True

        async def get_counterparty_by_phone(self, phone_number: str):
            captured["counterparty_phone"] = phone_number
            return {"id": str(counterparty_id)}

    async def fake_get_user_by_telegram_user_id(*_args, **_kwargs):
        return None

    async def fake_get_user_by_phone_number(*_args, **_kwargs):
        return None

    async def fake_create_user(db_arg, user_create, commit: bool = False):
        captured["db"] = db_arg
        captured["user_create"] = user_create
        captured["commit"] = commit
        return created_user

    monkeypatch.setattr("src.app.services.auth.service.get_user_by_telegram_user_id", fake_get_user_by_telegram_user_id)
    monkeypatch.setattr("src.app.services.auth.service.get_user_by_phone_number", fake_get_user_by_phone_number)
    monkeypatch.setattr("src.app.services.auth.service.create_user", fake_create_user)
    monkeypatch.setattr("src.app.services.auth.service.hash_password", lambda _password: "hashed-random-password")

    user, reason = await link_telegram_contact_to_user(
        db,
        telegram_user_id=902,
        phone_number="79990001123",
        first_name="Telegram",
        last_name="Buyer",
        username="buyer2",
        moysklad_client=FakeMoySkladClient(),
    )

    user_create = captured["user_create"]
    assert user is created_user
    assert reason is None
    assert captured["counterparty_phone"] == "+79990001123"
    assert captured["db"] is db
    assert captured["commit"] is False
    assert user_create.phone_number == "+79990001123"
    assert user_create.moysklad_counterparty_id == counterparty_id
    assert user_create.telegram_user_id == 902
    assert db.committed is True
    assert db.refreshed_user is created_user
