from fastapi.testclient import TestClient

from src.app.main import app
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
