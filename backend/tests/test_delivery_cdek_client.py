import pytest

from src.integrations.delivery.cdek.client import AsyncCDEKClient


@pytest.mark.anyio
async def test_calculate_delivery_falls_back_when_weight_and_currency_are_missing(monkeypatch: pytest.MonkeyPatch):
    client = AsyncCDEKClient(
        account="test-account",
        secure_password="test-password",
        base_url="https://api.cdek.test",
    )

    async def fake_city_code_by_coordinates(_latitude: float, _longitude: float) -> int:
        return 44

    async def fake_request(method: str, path: str, **kwargs):
        if method == "POST" and path == "/v2/calculator/tarifflist":
            return {
                "tariff_codes": [
                    {
                        "tariff_code": 136,
                        "delivery_sum": 199.0,
                        "period_min": 2,
                        "period_max": 4,
                    },
                ],
            }
        raise AssertionError(f"Unexpected request: {method} {path} {kwargs}")

    monkeypatch.setattr(client, "get_city_code_by_coordinates", fake_city_code_by_coordinates)
    monkeypatch.setattr(client, "_request", fake_request)

    try:
        calculation = await client.calculate_delivery(
            latitude=55.75628,
            longitude=37.616173,
            mode="office",
            country_code="RU",
            postal_code="125009",
            address="Москва",
            city="Москва",
        )
    finally:
        await client.aclose()

    assert calculation.delivery_sum == 199.0
    assert calculation.period_min == 2
    assert calculation.period_max == 4
    assert calculation.weight_calc == client.cargo["weight"]
    assert calculation.currency == "RUB"
