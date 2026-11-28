from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.app.modules.payments.diagnostics import PaymentRoute
from src.app.services import delivery_quotes
from src.integrations.bitrix_delivery import BitrixDeliveryError
from src.integrations.delivery.cdek.client import AsyncCDEKClient


def test_declined_payment_is_searchable_without_logging_request_secrets(caplog):
    app = FastAPI()
    routes = APIRouter(route_class=PaymentRoute)

    def reject():
        raise HTTPException(409, {"code": "settlement_pending", "message": "private-provider-data"})

    @routes.post("/create")
    def create(body: dict, _=Depends(reject)):
        raise AssertionError("must not start payment")

    app.include_router(routes)
    response = TestClient(app).post("/create", json={"order_id": 42, "secret": "private-client-data"})
    assert response.status_code == 409
    assert "order_id=42" in caplog.text and "reason=settlement_pending" in caplog.text
    assert "private-" not in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize("kind,count", [("found", 2), ("unknown", 1), ("ambiguous", 1), ("no_tariff", 1)])
async def test_delivery_city_fallback_never_invents_quote(monkeypatch, kind, count):
    guid = "00000000-0000-4000-8000-000000000011"
    entry = {"code": 17, "country_code": "RU", "fias_guid": guid}
    cities = [entry] if kind == "found" else ([entry, entry] if kind == "ambiguous" else [])
    lookup = AsyncMock(return_value=cities)
    cdek = SimpleNamespace(_request=lookup, get_delivery_point_city_code=AsyncMock(return_value=17))
    cdek.city_fias_guid = lambda code: AsyncCDEKClient.city_fias_guid(cdek, code)
    calls = []
    async def quote(**kwargs):
        calls.append(dict(kwargs["destination"]))
        if calls[-1].get("fias_guid") == guid:
            return {"delivery_sum": 345}
        raise BitrixDeliveryError(status_code=422, code="calculation_failed" if kind == "no_tariff" else "destination_not_found",
                                  message_ru="old message", message_en="old message")
    monkeypatch.setattr(delivery_quotes, "BitrixDeliveryClient", lambda: SimpleNamespace(quote=quote))
    monkeypatch.setattr(delivery_quotes, "build_bitrix_delivery_items", AsyncMock(return_value=[]))
    pending = delivery_quotes.calculate_authoritative_cdek_quote(
        None, user=SimpleNamespace(email="test@example.com"), items=[], cdek=cdek,
        address=dict(provider="CDEK", mode="pickup", provider_reference="SYA6", latitude=70, longitude=72, country_code="RU"))
    if kind == "found":
        assert (await pending)["delivery_sum"] == 345
    else:
        with pytest.raises(HTTPException, match="Выберите другой") as info:
            await pending
        assert info.value.status_code == 422
    assert len(calls) == count
    assert "fias_guid" not in calls[0]
    assert lookup.await_count == (0 if kind == "no_tariff" else 1)
