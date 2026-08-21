import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.app.main import app
from src.app.modules.delivery.cdek import router as cdek_router_module
from src.integrations.delivery.cdek import get_cdek_client
from src.integrations.delivery.schemas import COUNTRY_NAMES

SUPPORTED_COUNTRY_CODES = tuple(COUNTRY_NAMES.keys())


class FakeCDEKClient:
    def __init__(self) -> None:
        self.country_codes: list[str] = []

    async def get_delivery_point_markers(self, country_code: str = "RU") -> list[dict]:
        self.country_codes.append(country_code)
        return []


def test_delivery_point_markers_accepts_all_supported_country_codes():
    for country_code in SUPPORTED_COUNTRY_CODES:
        fake_cdek_client = FakeCDEKClient()
        app.dependency_overrides[get_cdek_client] = lambda: fake_cdek_client
        try:
            with TestClient(app) as test_client:
                response = test_client.get(
                    "/api/v1/delivery/cdek/delivery-point-markers",
                    params={"country_code": country_code},
                )

            assert response.status_code == 200
            assert response.json() == []
            assert fake_cdek_client.country_codes == [country_code]
        finally:
            app.dependency_overrides.pop(get_cdek_client, None)


def test_delivery_point_markers_rejects_unsupported_eu_country_code():
    fake_cdek_client = FakeCDEKClient()
    app.dependency_overrides[get_cdek_client] = lambda: fake_cdek_client
    try:
        with TestClient(app) as test_client:
            response = test_client.get(
                "/api/v1/delivery/cdek/delivery-point-markers",
                params={"country_code": "EU"},
            )

        assert response.status_code == 422
        assert fake_cdek_client.country_codes == []
    finally:
        app.dependency_overrides.pop(get_cdek_client, None)


def test_delivery_calculation_uses_owned_order_draft_items(monkeypatch):
    draft_items = [SimpleNamespace(variant_id=17, quantity=2)]

    async def fake_get_order_draft(_db, draft_id: int, *, user_id: int):
        assert draft_id == 42
        assert user_id == 7
        return SimpleNamespace(items=draft_items)

    async def fake_get_basket(*_args, **_kwargs):
        raise AssertionError("The live basket must not be read for a draft calculation")

    async def fake_quote(_db, *, user, address, items, cdek=None):
        assert user.id == 7
        assert address["provider_reference"] == "MSK1"
        assert items is draft_items
        assert cdek is not None
        return {
            "delivery_sum": 199.0,
            "period_min": 2,
            "period_max": 4,
            "weight_calc": 357,
            "currency": "RUB",
        }

    monkeypatch.setattr(cdek_router_module, "get_order_draft_by_id", fake_get_order_draft)
    monkeypatch.setattr(cdek_router_module, "get_basket_by_user_id", fake_get_basket)
    monkeypatch.setattr(cdek_router_module, "calculate_authoritative_cdek_quote", fake_quote)

    result = asyncio.run(cdek_router_module.cdek_delivery_calculate(
        latitude=55.75,
        longitude=37.61,
        mode="office",
        country_code="RU",
        postal_code="125009",
        address="Москва",
        city="Москва",
        delivery_point_code="MSK1",
        draft_id=42,
        db=object(),
        current_user=SimpleNamespace(id=7, email="buyer@example.com"),
        cdek=FakeCDEKClient(),
    ))

    assert result.delivery_sum == 199.0
    assert result.period_min == 2
    assert result.period_max == 4
