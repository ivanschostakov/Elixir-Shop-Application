from fastapi.testclient import TestClient

from src.app.main import app
from src.app.modules.delivery.yandex import router as yandex_router_module
from src.integrations.delivery.yandex import get_yandex_delivery_client


class FakeYandexClient:
    def __init__(self) -> None:
        self.call_count = 0

    async def get_delivery_point_markers(self):
        self.call_count += 1
        return []


def test_yandex_delivery_point_markers_returns_empty_when_toggle_disabled(monkeypatch):
    fake_yandex_client = FakeYandexClient()
    app.dependency_overrides[get_yandex_delivery_client] = lambda: fake_yandex_client
    monkeypatch.setattr(yandex_router_module, "YANDEX_DELIVERY_POINTS_ENABLED", False)
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/delivery/yandex/delivery-point-markers")

        assert response.status_code == 200
        assert response.json() == []
        assert fake_yandex_client.call_count == 0
    finally:
        app.dependency_overrides.pop(get_yandex_delivery_client, None)


def test_yandex_delivery_point_markers_calls_provider_when_toggle_enabled(monkeypatch):
    fake_yandex_client = FakeYandexClient()
    app.dependency_overrides[get_yandex_delivery_client] = lambda: fake_yandex_client
    monkeypatch.setattr(yandex_router_module, "YANDEX_DELIVERY_POINTS_ENABLED", True)
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/delivery/yandex/delivery-point-markers")

        assert response.status_code == 200
        assert response.json() == []
        assert fake_yandex_client.call_count == 1
    finally:
        app.dependency_overrides.pop(get_yandex_delivery_client, None)
