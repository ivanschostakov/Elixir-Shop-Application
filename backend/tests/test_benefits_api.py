import sys
import types
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

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

from config import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER
from src.database.models import User
from src.integrations.bitrix_promo import BitrixPromo

SYNC_DB_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
sync_engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)


def _decimal(value) -> Decimal:
    return Decimal(str(value))


def _delete_user(user_id: int) -> None:
    with Session(sync_engine) as session:
        user = session.get(User, user_id)
        if user is None:
            return
        session.delete(user)
        session.commit()


def _set_user_promo_code(user_id: int, code: str | None) -> None:
    with Session(sync_engine) as session:
        user = session.get(User, user_id)
        if user is None:
            return
        user.promo_code = code
        session.commit()


@pytest.fixture()
def registered_user(register_verified_user):
    token = uuid.uuid4().hex[:12]
    payload = register_verified_user({
        "username": f"u{token}",
        "email": f"benefits_{token}@example.com",
        "password": "test-password",
        "name": "Benefit",
        "surname": "Tester",
    })
    user_id = payload["user"]["id"]

    try:
        yield {"user_id": user_id, "headers": {"Authorization": f"Bearer {payload['access_token']}"}}
    finally:
        _delete_user(user_id)


def test_benefit_check_returns_referral_discount_only(client: TestClient, registered_user):
    _set_user_promo_code(registered_user["user_id"], "WELCOME")

    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"code": "  WELCOME  ", "subtotal": "200.00", "currency": "RUB"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["subtotal_source"] == "request"
    assert _decimal(payload["basket_subtotal"]) == Decimal("200.00")
    assert payload["entered_code"] == "WELCOME"
    assert payload["unresolved_code_reason"] is None
    assert len(payload["entered_code_matches"]) == 1
    assert payload["entered_code_matches"][0]["source_kind"] == "app_referral"
    assert payload["entered_code_matches"][0]["is_applicable"] is True
    assert _decimal(payload["entered_code_matches"][0]["estimated_discount_amount"]) == Decimal("6.00")
    assert payload["personal_discount"]["source_kind"] == "app_referral"
    assert _decimal(payload["personal_discount"]["estimated_discount_amount"]) == Decimal("6.00")
    assert payload["best_discount"]["source_kind"] == "app_referral"
    assert _decimal(payload["best_discount"]["estimated_discount_amount"]) == Decimal("6.00")
    assert len(payload["available_discount_options"]) == 1
    assert payload["available_discount_options"][0]["source_kind"] == "app_referral"
    assert _decimal(payload["available_discount_options"][0]["discount_percent"]) == Decimal("3.00")
    assert [option["source_kind"] for option in payload["stacked_discount_options"]] == ["app_referral"]


def test_benefit_check_applies_referral_discount_to_discountable_subtotal_only(client: TestClient, registered_user):
    _set_user_promo_code(registered_user["user_id"], "WELCOME")

    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"code": "WELCOME", "subtotal": "200.00", "discountable_subtotal": "100.00", "currency": "RUB"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["entered_code_matches"]) == 1
    assert payload["entered_code_matches"][0]["source_kind"] == "app_referral"
    assert _decimal(payload["stacked_discount_amount"]) == Decimal("3.00")
    assert _decimal(payload["total_after_discounts"]) == Decimal("197.00")


def test_benefit_check_resolves_entered_code_through_bitrix_php(client: TestClient, registered_user, monkeypatch: pytest.MonkeyPatch):
    async def fake_get_promo(code: str):
        assert code == "Огонь26"
        return BitrixPromo(code="Огонь26", discount_percent=Decimal("7"))

    monkeypatch.setattr("src.app.services.benefits.service.bitrix_promo_client.is_configured", lambda: True)
    monkeypatch.setattr("src.app.services.benefits.service.bitrix_promo_client.get_promo", fake_get_promo)

    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"code": "Огонь26", "subtotal": "200.00", "discountable_subtotal": "100.00", "currency": "RUB"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["unresolved_code_reason"] is None
    assert len(payload["entered_code_matches"]) == 1
    assert payload["entered_code_matches"][0]["source_kind"] == "bitrix_promo"
    assert _decimal(payload["entered_code_matches"][0]["discount_percent"]) == Decimal("7.00")
    assert _decimal(payload["stacked_discount_amount"]) == Decimal("7.00")
    assert _decimal(payload["total_after_discounts"]) == Decimal("193.00")
