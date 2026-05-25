import asyncio
from types import SimpleNamespace

from src.app.services.orders import creation


class _GeoClientStub:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def geocode(self, address: str, lang: str = "ru_RU", results: int = 1):
        self.queries.append(address)
        return SimpleNamespace(
            city="Москва",
            postal_code="123557",
            country_code="RU",
            country="Россия",
            region="Москва",
            street="пер. Большой Тишинский",
            house="26",
        )


def test_enrich_selected_delivery_address_payload_adds_geocode_components(monkeypatch):
    geo_client = _GeoClientStub()
    monkeypatch.setattr(creation, "get_geo_client", lambda: geo_client)
    payload = {
        "address": "пер. Большой Тишинский, 26",
        "full_address": "123557, Россия, Москва, пер. Большой Тишинский, 26",
        "country_code": "RU",
        "latitude": 55.7708,
        "longitude": 37.5829,
    }

    asyncio.run(creation._enrich_selected_delivery_address_payload(payload))

    assert geo_client.queries == ["37.582900,55.770800"]
    assert payload["city"] == "Москва"
    assert payload["postal_code"] == "123557"
    assert payload["country_code"] == "RU"
    assert payload["country"] == "Россия"
    assert payload["region"] == "Москва"
    assert payload["street"] == "пер. Большой Тишинский"
    assert payload["house"] == "26"
