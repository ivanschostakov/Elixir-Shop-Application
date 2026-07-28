import json
import asyncio

import httpx
import pytest

from src.integrations.bitrix_promo import BitrixPromoClient, BitrixPromoError


TOKEN = "a" * 64


def test_lookup_uses_server_token_and_returns_data(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Elixir-Promo-Token"] == TOKEN
        assert json.loads(request.content) == {"action": "lookup", "promo": "TEST"}
        return httpx.Response(
            200,
            json={"ok": True, "action": "lookup", "data": {"promo": "TEST", "discount_id": 24}},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )

    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    assert asyncio.run(client.lookup("TEST")) == {"promo": "TEST", "discount_id": 24}


def test_error_preserves_russian_and_english_messages(monkeypatch):
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "ok": False,
                "error": "promo_not_found",
                "message_ru": "Промокод не найден.",
                "message_en": "Promo code was not found.",
            },
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )

    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    with pytest.raises(BitrixPromoError) as raised:
        asyncio.run(client.lookup("MISSING"))

    assert raised.value.status_code == 404
    assert raised.value.code == "promo_not_found"
    assert raised.value.message_ru == "Промокод не найден."
    assert raised.value.message_en == "Promo code was not found."


def test_quote_supports_email_user_context(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "action": "quote",
            "promo": "TEST",
            "items": [{"product_system_id": "product-1", "quantity": 1}],
            "user_email": "customer@example.com",
        }
        return httpx.Response(
            200,
            json={"ok": True, "data": {"promo": "TEST", "user_context": "matched_by_email"}},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    result = asyncio.run(
        client.quote(
            promo="TEST",
            items=[{"product_system_id": "product-1", "quantity": 1}],
            user_email="customer@example.com",
        )
    )
    assert result["user_context"] == "matched_by_email"


@pytest.mark.parametrize(
    ("method_name", "expected_payload"),
    [
        (
            "context",
            {
                "action": "context",
                "promo": "REFERRER",
                "user_email": "customer@example.com",
            },
        ),
        (
            "attach_referrer",
            {
                "action": "attach_referrer",
                "promo": "REFERRER",
                "user_email": "customer@example.com",
            },
        ),
    ],
)
def test_user_promo_actions_include_customer_context(monkeypatch, method_name, expected_payload):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == expected_payload
        return httpx.Response(
            200,
            json={"ok": True, "data": {"user_context": "matched_by_email"}},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    method = getattr(client, method_name)
    result = asyncio.run(
        method(
            promo="REFERRER",
            user_email="customer@example.com",
        )
    )
    assert result["user_context"] == "matched_by_email"


def test_detach_referrer_includes_customer_context(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "action": "detach_referrer",
            "user_email": "customer@example.com",
        }
        return httpx.Response(200, json={"ok": True, "data": {"outcome": "detached"}})

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    result = asyncio.run(client.detach_referrer(user_email="customer@example.com"))
    assert result["outcome"] == "detached"


@pytest.mark.parametrize(
    ("method_name", "action", "response_data"),
    [
        (
            "quote_referral_accrual",
            "quote_referral_accrual",
            {"storage": "app", "bitrix_writes": False, "accruals": []},
        ),
        (
            "record_paid_purchase",
            "record_paid_purchase",
            {"outcome": "recorded", "purchase": {"id": 17}},
        ),
    ],
)
def test_paid_order_actions_send_idempotent_order_identity(
    monkeypatch,
    method_name,
    action,
    response_data,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "action": action,
            "external_order_id": "EP-ORDER01",
            "user_email": "customer@example.com",
            "promo": "REFERRER",
            "amount": "12500.00",
            "currency": "RUB",
            "paid_at": "2026-07-28T12:00:00+00:00",
        }
        return httpx.Response(
            200,
            json={"ok": True, "data": response_data},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    method = getattr(client, method_name)
    result = asyncio.run(
        method(
            external_order_id="EP-ORDER01",
            user_email="customer@example.com",
            promo="REFERRER",
            amount="12500.00",
            currency="RUB",
            paid_at="2026-07-28T12:00:00+00:00",
        )
    )
    assert result == response_data


def test_referral_eligibility_uses_bitrix_user_identity(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "action": "referral_eligibility",
            "period": "2026-06",
            "user_id": 396,
        }
        return httpx.Response(
            200,
            json={
                "ok": True,
                "data": {
                    "status": "approved",
                    "period": "2026-06",
                    "user_id": 396,
                },
            },
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    result = asyncio.run(
        client.referral_eligibility(
            period="2026-06",
            bitrix_user_id=396,
        )
    )
    assert result["status"] == "approved"


def test_empty_configuration_is_rejected(monkeypatch):
    monkeypatch.setattr("src.integrations.bitrix_promo.BITRIX_PROMO_ENDPOINT", None)
    monkeypatch.setattr("src.integrations.bitrix_promo.BITRIX_PROMO_TOKEN", None)
    with pytest.raises(RuntimeError, match="not configured"):
        BitrixPromoClient()
