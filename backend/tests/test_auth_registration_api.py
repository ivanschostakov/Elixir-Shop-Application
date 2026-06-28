from types import SimpleNamespace

import pytest

from src.app.modules.auth.schemas.register import UserRegisterPayload
from src.app.services.auth.service import register_user


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


def test_user_register_payload_normalizes_phone_and_email():
    payload = UserRegisterPayload(
        username=" phoneuser ",
        email=" PhoneUser@Example.com ",
        password="supersecret",
        name=" Phone ",
        surname=" User ",
        phone_number=" +7 (999) 000-11-22 ",
    )

    assert payload.username == "phoneuser"
    assert payload.email == "phoneuser@example.com"
    assert payload.name == "Phone"
    assert payload.surname == "User"
    assert payload.phone_number == "+7 (999) 000-11-22"


@pytest.mark.anyio
async def test_register_user_passes_phone_number_to_user_create(monkeypatch: pytest.MonkeyPatch):
    payload = UserRegisterPayload(
        username="phoneuser",
        email="phoneuser@example.com",
        password="supersecret",
        name="Phone",
        surname="User",
        phone_number="+79990001122",
    )
    db = _DummyDbSession()
    request = object()
    created_user = SimpleNamespace(id=17, email=payload.email)
    captured: dict[str, object] = {}

    async def fake_apply_auth_rate_limit(request_arg, *, scope: str, principal: str | None = None, verify: bool = False):
        captured["rate_limit"] = {
            "request": request_arg,
            "scope": scope,
            "principal": principal,
            "verify": verify,
        }

    def fake_hash_password(password: str) -> str:
        captured["password"] = password
        return "hashed-password"

    async def fake_create_user(db_arg, user_create, commit: bool = False):
        captured["db"] = db_arg
        captured["user_create"] = user_create
        captured["commit"] = commit
        return created_user

    async def fake_create_and_send_verification_code(user, db_arg):
        captured["verification_user"] = user
        captured["verification_db"] = db_arg

    monkeypatch.setattr("src.app.services.auth.service._apply_auth_rate_limit", fake_apply_auth_rate_limit)
    monkeypatch.setattr("src.app.services.auth.service.hash_password", fake_hash_password)
    monkeypatch.setattr("src.app.services.auth.service.create_user", fake_create_user)
    monkeypatch.setattr("src.app.services.auth.service._create_and_send_verification_code", fake_create_and_send_verification_code)

    response = await register_user(request, payload, db)

    user_create = captured["user_create"]
    assert captured["rate_limit"] == {
        "request": request,
        "scope": "auth:register",
        "principal": payload.email,
        "verify": False,
    }
    assert captured["password"] == payload.password
    assert captured["db"] is db
    assert captured["commit"] is False
    assert user_create.phone_number == payload.phone_number
    assert user_create.email == payload.email
    assert user_create.username == payload.username
    assert captured["verification_user"] is created_user
    assert captured["verification_db"] is db
    assert db.committed is True
    assert db.refreshed_user is created_user
    assert response.user_id == created_user.id
    assert response.email == created_user.email
