from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from src.integrations.website_identity import WebsiteIdentityClient, WebsiteIdentityError


def test_authenticate_sends_credentials_and_private_header(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_post(self, url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        captured["headers"] = kwargs["headers"]
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            content=json.dumps(
                {
                    "ok": True,
                    "data": {
                        "user": {"id": 42, "email": "customer@example.com"},
                        "discounts": {},
                    },
                }
            ).encode(),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    client = WebsiteIdentityClient(
        endpoint="https://example.test/local/api/app_integration.php",
        token="x" * 32,
    )

    result = asyncio.run(client.authenticate(login="customer@example.com", password="secret-pass"))

    assert result["user"]["id"] == 42
    assert captured["json"] == {"login": "customer@example.com", "password": "secret-pass"}
    assert captured["headers"]["X-App-Integration-Token"] == "x" * 32


def test_authenticate_translates_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self, url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(
            401,
            request=request,
            json={
                "ok": False,
                "error": "invalid_credentials",
                "message_ru": "Неверный логин или пароль.",
                "message_en": "Invalid login or password.",
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    client = WebsiteIdentityClient(endpoint="https://example.test/api", token="y" * 32)

    with pytest.raises(WebsiteIdentityError) as error:
        asyncio.run(client.authenticate(login="customer@example.com", password="wrong-pass"))

    assert error.value.status_code == 401
    assert error.value.code == "invalid_credentials"
    assert error.value.message_ru == "Неверный логин или пароль."
