import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
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


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def stub_email_verification(monkeypatch: pytest.MonkeyPatch):
    import src.app.modules.auth.router as auth_router_module

    async def fake_send_user_verification_code_email(*, to_email: str, code: str) -> None:
        return None

    monkeypatch.setattr(auth_router_module, "generate_email_verification_code", lambda: TEST_EMAIL_VERIFICATION_CODE)
    monkeypatch.setattr(auth_router_module, "send_user_verification_code_email", fake_send_user_verification_code_email)


@pytest.fixture(autouse=True)
def disable_app_integrity_by_default(monkeypatch: pytest.MonkeyPatch):
    import src.app.services.app_integrity.common as app_integrity_common

    monkeypatch.setattr(app_integrity_common, "APP_INTEGRITY_MODE", "off")


@pytest.fixture()
def register_verified_user(client: TestClient):
    def _register(payload: dict) -> dict:
        payload = {"phone_number": "+79990000000", **payload}
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201, response.text

        verify_response = client.post(
            "/api/v1/auth/register/verify",
            json={"email": payload["email"], "code": TEST_EMAIL_VERIFICATION_CODE},
        )
        assert verify_response.status_code == 200, verify_response.text
        return verify_response.json()

    return _register
