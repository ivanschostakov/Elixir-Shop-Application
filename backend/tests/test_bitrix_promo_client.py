import asyncio

from decimal import Decimal

import httpx
import pytest

from src.integrations.bitrix_promo import BitrixPromoClient, BitrixPromoIntegrationError


def test_get_promo_calls_bitrix_php_with_code_and_token():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["token"] = request.headers.get("X-Promo-Token")
        return httpx.Response(200, json={"ok": True, "promo": "Огонь26", "discount_percent": 3})

    client = BitrixPromoClient(
        endpoint="https://example.com/local/api/get_promo.php",
        token="promo-secret",
        transport=httpx.MockTransport(handler),
    )
    promo = asyncio.run(client.get_promo("Огонь26"))

    assert promo is not None
    assert promo.code == "Огонь26"
    assert promo.discount_percent == Decimal("3")
    assert "promo=%D0%9E%D0%B3%D0%BE%D0%BD%D1%8C26" in captured["url"]
    assert captured["token"] == "promo-secret"


def test_get_promo_returns_none_for_unknown_or_inactive_code():
    client = BitrixPromoClient(
        endpoint="https://example.com/local/api/get_promo.php",
        transport=httpx.MockTransport(lambda _: httpx.Response(404, json={"ok": False, "error": "promo_not_found"})),
    )

    assert asyncio.run(client.get_promo("UNKNOWN")) is None


def test_get_promo_rejects_invalid_discount_percent():
    client = BitrixPromoClient(
        endpoint="https://example.com/local/api/get_promo.php",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"ok": True, "promo": "BAD", "discount_percent": 0})),
    )

    with pytest.raises(BitrixPromoIntegrationError):
        asyncio.run(client.get_promo("BAD"))
