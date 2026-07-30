import asyncio
import hashlib
import hmac
import json

import httpx
import pytest

from src.integrations.bitrix_delivery import BitrixDeliveryClient, BitrixDeliveryError


SECRET = "d" * 64


def test_quote_is_signed_and_returns_bitrix_result(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        timestamp = request.headers["X-Elixir-Timestamp"]
        expected = hmac.new(
            SECRET.encode(),
            timestamp.encode() + b"." + request.content,
            hashlib.sha256,
        ).hexdigest()
        assert hmac.compare_digest(request.headers["X-Elixir-Signature"], expected)
        assert json.loads(request.content) == {
            "action": "quote",
            "destination": {
                "address": "Красная площадь, 1",
                "cdek_city_code": 44,
                "city": "Москва",
            },
            "items": [
                {
                    "product_system_id": "product-id",
                    "quantity": 2,
                    "variant_system_id": "variant-id",
                }
            ],
            "mode": "pickup",
            "user_email": "customer@example.com",
        }
        return httpx.Response(
            200,
            json={
                "ok": True,
                "data": {
                    "delivery_sum": 345.26,
                    "period_min": 2,
                    "period_max": 3,
                    "weight_calc": 714,
                    "currency": "RUB",
                },
            },
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_delivery.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixDeliveryClient(endpoint="https://example.test/quote.php", secret=SECRET)
    result = asyncio.run(
        client.quote(
            mode="pickup",
            destination={
                "cdek_city_code": 44,
                "city": "Москва",
                "address": "Красная площадь, 1",
            },
            items=[
                {
                    "variant_system_id": "variant-id",
                    "product_system_id": "product-id",
                    "quantity": 2,
                }
            ],
            user_email="customer@example.com",
        )
    )
    assert result["delivery_sum"] == 345.26


def test_error_preserves_bilingual_messages(monkeypatch):
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "ok": False,
                "error": "delivery_mode_unavailable",
                "message_ru": "Выбранный способ доставки отключён в настройках сайта.",
                "message_en": "Selected delivery mode is disabled in site settings.",
            },
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_delivery.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixDeliveryClient(endpoint="https://example.test/quote.php", secret=SECRET)
    with pytest.raises(BitrixDeliveryError) as raised:
        asyncio.run(client.quote(mode="door", destination={}, items=[]))
    assert raised.value.code == "delivery_mode_unavailable"
    assert raised.value.message_ru == "Выбранный способ доставки отключён в настройках сайта."
    assert raised.value.message_en == "Selected delivery mode is disabled in site settings."


def test_empty_configuration_is_rejected(monkeypatch):
    monkeypatch.setattr("src.integrations.bitrix_delivery.BITRIX_DELIVERY_ENDPOINT", None)
    monkeypatch.setattr("src.integrations.bitrix_delivery.BITRIX_DELIVERY_SECRET", None)
    with pytest.raises(RuntimeError, match="not configured"):
        BitrixDeliveryClient()
