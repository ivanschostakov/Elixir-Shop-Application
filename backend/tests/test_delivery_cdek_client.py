import pytest

from src.integrations.delivery.cdek.client import AsyncCDEKClient


@pytest.mark.anyio
async def test_calculate_delivery_falls_back_when_weight_and_currency_are_missing(monkeypatch: pytest.MonkeyPatch):
    client = AsyncCDEKClient(
        account="test-account",
        secure_password="test-password",
        base_url="https://api.cdek.test",
    )

    async def fake_resolve_city_code(**_kwargs) -> int:
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

    monkeypatch.setattr(client, "resolve_city_code", fake_resolve_city_code)
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


@pytest.mark.anyio
async def test_get_delivery_point_city_code_uses_exact_point(monkeypatch: pytest.MonkeyPatch):
    client = AsyncCDEKClient(
        account="test-account",
        secure_password="test-password",
        base_url="https://api.cdek.test",
    )

    async def fake_request(method: str, path: str, **kwargs):
        assert method == "GET"
        assert path == "/v2/deliverypoints"
        assert kwargs["params"] == {"code": "MSK2"}
        return [
            {
                "code": "MSK2",
                "location": {
                    "city_code": 44,
                    "city": "Москва",
                    "country_code": "RU",
                },
            }
        ]

    monkeypatch.setattr(client, "_request", fake_request)

    try:
        city_code = await client.get_delivery_point_city_code("MSK2", country_code="RU")
    finally:
        await client.aclose()

    assert city_code == 44


@pytest.mark.anyio
async def test_resolve_city_code_uses_strict_address_and_nearest_exact_city(
    monkeypatch: pytest.MonkeyPatch,
):
    client = AsyncCDEKClient(
        account="test-account",
        secure_password="test-password",
        base_url="https://api.cdek.test",
    )

    async def fake_request(method: str, path: str, **kwargs):
        assert method == "GET"
        assert path == "/v2/location/cities"
        assert kwargs["params"] == {
            "city": "Москва",
            "country_codes": "RU",
            "postal_code": "101000",
            "size": 100,
            "page": 0,
        }
        return [
            {
                "code": 1913777,
                "city": "Москва",
                "region": "Тверская область",
                "country_code": "RU",
                "latitude": 56.917778,
                "longitude": 32.163334,
            },
            {
                "code": 44,
                "city": "Москва",
                "region": "Москва",
                "country_code": "RU",
                "latitude": 55.75322,
                "longitude": 37.622513,
            },
            {
                "code": 5,
                "city": "Усинск",
                "region": "Республика Коми",
                "country_code": "RU",
                "latitude": 65.995028,
                "longitude": 57.557139,
            },
        ]

    monkeypatch.setattr(client, "_request", fake_request)

    try:
        city_code = await client.resolve_city_code(
            latitude=55.7558,
            longitude=37.6176,
            city="Москва",
            postal_code="101000",
            country_code="RU",
        )
    finally:
        await client.aclose()

    assert city_code == 44


@pytest.mark.anyio
async def test_resolve_city_code_fails_closed_for_ambiguous_destination(
    monkeypatch: pytest.MonkeyPatch,
):
    client = AsyncCDEKClient(
        account="test-account",
        secure_password="test-password",
        base_url="https://api.cdek.test",
    )

    async def fake_request(_method: str, _path: str, **_kwargs):
        return [
            {
                "code": 100,
                "city": "Тест",
                "country_code": "RU",
                "latitude": 55.75,
                "longitude": 37.61,
            },
            {
                "code": 101,
                "city": "Тест",
                "country_code": "RU",
                "latitude": 55.751,
                "longitude": 37.611,
            },
        ]

    monkeypatch.setattr(client, "_request", fake_request)

    try:
        with pytest.raises(Exception) as exception_info:
            await client.resolve_city_code(
                latitude=55.75,
                longitude=37.61,
                city="Тест",
                postal_code=None,
                country_code="RU",
            )
    finally:
        await client.aclose()

    assert getattr(exception_info.value, "status_code", None) == 422
