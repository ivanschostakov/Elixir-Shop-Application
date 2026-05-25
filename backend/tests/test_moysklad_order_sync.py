import asyncio
from types import SimpleNamespace
from uuid import UUID

from src.integrations.moysklad import order_sync


class _MoySkladClientStub:
    async def find_country_by_name_or_code(self, *values: str):
        normalized = {value.strip().upper() for value in values if value and value.strip()}
        if "RU" in normalized or "РОССИЯ" in normalized:
            return {
                "id": "b6f25f13-e3df-46a8-b4d5-64c10e955f4d",
                "meta": {
                    "href": "https://api.moysklad.ru/api/remap/1.2/entity/country/b6f25f13-e3df-46a8-b4d5-64c10e955f4d",
                    "type": "country",
                    "mediaType": "application/json",
                },
            }
        return None

    async def find_region_by_name(self, name: str, *, country_id: UUID | None = None):
        normalized = (name or "").strip().lower()
        if normalized in {"москва", "г. москва"}:
            return {
                "id": "f9358e5f-f82f-482e-b204-6089f290f9c9",
                "meta": {
                    "href": "https://api.moysklad.ru/api/remap/1.2/entity/region/f9358e5f-f82f-482e-b204-6089f290f9c9",
                    "type": "region",
                    "mediaType": "application/json",
                },
            }
        return None


def test_shipment_address_full_includes_structured_fields_and_refs():
    order = SimpleNamespace(
        selected_delivery_payload={
            "address": {
                "full_address": "123557, Россия, Москва, пер. Большой Тишинский, 26, корп. 15-16, кв. 88",
                "city": "Москва",
                "postal_code": "123557",
                "country_code": "RU",
                "street": "пер. Большой Тишинский",
                "house": "26, корп. 15-16",
                "apartment": "88",
                "region": "Москва",
                "details": "Подъезд 2",
            }
        },
        delivery_address=SimpleNamespace(
            city="Москва",
            postal_code="123557",
            details="Подъезд 2",
            country_code="RU",
        ),
        delivery_string=None,
    )

    result = asyncio.run(order_sync._shipment_address_full(order, moysklad_client=_MoySkladClientStub()))

    assert result is not None
    assert result["city"] == "Москва"
    assert result["postalCode"] == "123557"
    assert result["street"] == "пер. Большой Тишинский"
    assert result["house"] == "26, корп. 15-16"
    assert result["apartment"] == "88"
    assert result["comment"] == "Подъезд 2"
    assert result["country"]["meta"]["type"] == "country"
    assert result["region"]["meta"]["type"] == "region"


def test_shipment_address_full_extracts_house_and_apartment_from_full_address():
    order = SimpleNamespace(
        selected_delivery_payload={
            "address": {
                "full_address": "123557, Россия, Москва, Москва, пер. Большой Тишинский, 26, корп. 15-16, кв. 88",
                "city": "Москва",
                "postal_code": "123557",
                "country_code": "RU",
            }
        },
        delivery_address=SimpleNamespace(
            city="Москва",
            postal_code="123557",
            details=None,
            country_code="RU",
        ),
        delivery_string=None,
    )

    result = asyncio.run(order_sync._shipment_address_full(order, moysklad_client=_MoySkladClientStub()))

    assert result is not None
    assert result["street"] == "пер. Большой Тишинский"
    assert result["house"] == "26, корп. 15-16"
    assert result["apartment"] == "88"
