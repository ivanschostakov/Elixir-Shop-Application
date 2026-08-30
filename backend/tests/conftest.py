import os
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

TEST_ENV = {
    "POSTGRES_DB": "test",
    "POSTGRES_USER": "test",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PASSWORD": "test",
    "JWT_ACCESS_SECRET_KEY": "test-only-secret-key",
    "OPENAI_API_KEY": "test-only-openai-key",
    "API_BASE_URL": "https://example.test",
    "PUBLIC_API_BASE_URL": "https://example.test",
    "AMOCRM_ACCOUNT_ID": "",
    "AMOCRM_WEBHOOK_ALLOWED_ACCOUNT_IDS": "",
    "AMOCRM_WEBHOOK_ALLOWED_SUBDOMAINS": "",
    "AMOCRM_WEBHOOK_ALLOWED_IPS": "",
    "CDEK_ACCOUNT": "test",
    "CDEK_SECURE_PASSWORD": "test",
    "CDEK_API_URL": "https://example.invalid",
    "YANDEX_DELIVERY_BASE_URL": "https://example.invalid",
    "YANDEX_DELIVERY_TOKEN": "test",
    "YANDEX_DELIVERY_WAREHOUSE_ID": "00000000-0000-0000-0000-000000000001",
}
for name, value in TEST_ENV.items():
    os.environ.setdefault(name, value)

if "PIL" not in sys.modules:
    pil_module = types.ModuleType("PIL")
    pil_module.Image = types.SimpleNamespace(open=None)

    class _UnidentifiedImageError(Exception):
        pass

    pil_module.UnidentifiedImageError = _UnidentifiedImageError
    sys.modules["PIL"] = pil_module

from src.app import main as app_main

app = app_main.app

TEST_EMAIL_VERIFICATION_CODE = "123456"


@pytest.fixture(autouse=True)
def isolate_dependency_overrides():
    app.dependency_overrides.clear()
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def stub_email_verification(monkeypatch: pytest.MonkeyPatch):
    import src.app.services.auth.service as auth_service_module

    async def fake_send_user_verification_code_email(*, to_email: str, code: str) -> None:
        return None

    monkeypatch.setattr(auth_service_module, "generate_email_verification_code", lambda: TEST_EMAIL_VERIFICATION_CODE)
    monkeypatch.setattr(auth_service_module, "send_user_verification_code_email", fake_send_user_verification_code_email)


@pytest.fixture(autouse=True)
def disable_app_integrity_by_default(monkeypatch: pytest.MonkeyPatch):
    import src.app.services.app_integrity.common as app_integrity_common

    monkeypatch.setattr(app_integrity_common, "APP_INTEGRITY_MODE", "off")


@pytest.fixture(autouse=True)
def stub_authoritative_bitrix_delivery(monkeypatch: pytest.MonkeyPatch):
    async def fake_quote(_session, *, user, address, items, cdek=None):
        mode = address.get("mode") if isinstance(address, dict) else getattr(address, "mode", None)
        is_door = mode == "door"
        return {
            "delivery_sum": 299.0 if is_door else 199.0,
            "period_min": 1 if is_door else 2,
            "period_max": 2 if is_door else 4,
            "weight_calc": 357,
            "currency": "RUB",
        }

    targets = (
        "src.app.modules.delivery.cdek.router.calculate_authoritative_cdek_quote",
        "src.app.services.basket.calculate_authoritative_cdek_quote",
        "src.app.services.guest_checkout.calculate_authoritative_cdek_quote",
        "src.app.services.orders.creation.calculate_authoritative_cdek_quote",
        "src.app.services.orders.drafts.calculate_authoritative_cdek_quote",
    )
    for target in targets:
        monkeypatch.setattr(target, fake_quote)


@pytest.fixture()
def register_verified_user(client: TestClient):
    def _register(payload: dict) -> dict:
        phone_number = payload.get("phone_number")
        payload = {
            key: value
            for key, value in payload.items()
            if key in {"email", "password", "name", "surname"}
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201, response.text

        verify_response = client.post(
            "/api/v1/auth/register/verify",
            json={"email": payload["email"], "code": TEST_EMAIL_VERIFICATION_CODE},
        )
        assert verify_response.status_code == 200, verify_response.text
        verified_payload = verify_response.json()
        if phone_number:
            profile_response = client.patch(
                "/api/v1/users/me/profile/personal-data",
                headers={"Authorization": f"Bearer {verified_payload['access_token']}"},
                json={"phone_number": phone_number},
            )
            assert profile_response.status_code == 200, profile_response.text
            verified_payload["user"] = profile_response.json()
        return verified_payload

    return _register
