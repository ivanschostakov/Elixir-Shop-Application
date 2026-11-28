import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from src.integrations.delivery.geo.schemas.code import parse_region
from src.integrations.delivery.schemas.delivery_point import DeliveryPoint
from src.integrations.moysklad.client.metadata import MetadataMixin
from src.integrations.moysklad.order_sync import address


def row(name, **more):
    return {"name": name, "meta": {"href": "region/" + str(uuid4())}, **more}


def test_region_lookup_is_unique_and_type_sensitive():
    c = MetadataMixin()
    adygea, moscow, oblast = row("Респ Адыгея"), row("г Москва"), row("Московская обл")
    foreign = row("Респ Башкортостан", country={"meta": {"href": "country/" + str(uuid4())}})
    c.get_all = AsyncMock(return_value=[adygea, moscow, oblast, foreign])
    lookup = lambda name: asyncio.run(c.find_region_by_name(name, country_id=uuid4()))
    assert lookup("Республика Адыгея") == adygea
    assert lookup("Москва") == moscow
    assert lookup("Московская область") == oblast
    assert lookup("Приволжский федеральный округ") is None
    assert lookup("Республика Башкортостан") is None
    assert lookup("Неизвестный край") is None
    c.get_all.return_value.append(row("Московская область"))
    assert lookup("Московская область") is None


@pytest.mark.parametrize("code,country,available,expected", [
    ("UFA1", "RU", True, True), ("UFA2", "RU", True, False),
    ("UFA1", "KZ", True, False), ("UFA1", "RU", False, False),
])
def test_ufa_uses_selected_pickup_not_first_dictionary_row(monkeypatch, code, country, available, expected):
    point = DeliveryPoint.from_cdek_dict({"code": code, "name": "ПВЗ", "location": {
        "city": "Уфа", "country_code": country, "region": "Республика Башкортостан"}})
    fetch = AsyncMock(return_value=point)
    if not available: fetch.side_effect = httpx.ConnectError("offline")
    monkeypatch.setattr(address, "get_cdek_client", lambda: SimpleNamespace(get_delivery_point=fetch))
    c = MetadataMixin()
    bash = row("Респ Башкортостан")
    c.get_all = AsyncMock(return_value=[row("Респ Адыгея"), bash])
    c.find_country_by_name_or_code = AsyncMock(return_value=None)
    order = SimpleNamespace(selected_delivery_service="CDEK", delivery_address=None, selected_delivery_payload={
        "deliveryMode": "office", "address": {"full_address": "Россия, Уфа", "country_code": "RU",
            "region": "Приволжский федеральный округ", "city": "Уфа", "code": "UFA1"}})
    result = asyncio.run(address._shipment_address_full(order, moysklad_client=c))
    fetch.assert_awaited_once_with("UFA1")
    assert result["city"] == "Уфа"
    assert result.get("region") == ({"meta": bash["meta"]} if expected else None)


def test_russian_geocode_skips_federal_district_but_keeps_autonomous_district():
    data = {"country_code": "RU", "Components": [{"kind": "province", "name": "Уральский федеральный округ"}]}
    assert parse_region(data) is None
    data["Components"].append({"kind": "province", "name": "Ямало-Ненецкий автономный округ"})
    assert parse_region(data) == "Ямало-Ненецкий автономный округ"
