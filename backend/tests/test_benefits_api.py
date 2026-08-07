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
from src.database.models import ReferralProfile, User

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


def _set_partner_program(
    user_id: int,
    purchase_total: str = "30000.00",
    *,
    promo_code: str | None = "REFERRER",
) -> None:
    with Session(sync_engine) as session:
        user = session.get(User, user_id)
        assert user is not None
        user.promo_code = promo_code
        profile = (
            session.query(ReferralProfile)
            .filter(ReferralProfile.user_id == user_id)
            .one_or_none()
        )
        if profile is None:
            profile = ReferralProfile(user_id=user_id)
            session.add(profile)
        profile.reward_program = "partner"
        profile.reward_program_selection_source = "user"
        profile.referral_discount_base_total = Decimal(purchase_total)
        profile.current_discount_percent = Decimal("3.00")
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


@pytest.fixture(autouse=True)
def disable_bitrix_promo_for_local_benefit_tests(monkeypatch):
    monkeypatch.setattr(
        "src.app.services.benefits.service.bitrix_promo_configured",
        lambda: False,
    )
    monkeypatch.setattr(
        "src.app.services.referrals.bitrix_sync.bitrix_promo_configured",
        lambda: False,
    )


def test_benefit_check_returns_referral_personal_discount(client: TestClient, registered_user):
    _set_partner_program(registered_user["user_id"])

    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"subtotal": "200.00", "currency": "RUB", "reward_mode": "promo"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["subtotal_source"] == "request"
    assert _decimal(payload["basket_subtotal"]) == Decimal("200.00")
    assert payload["reward_program"] == "partner"
    assert payload["program_selection_required"] is False
    assert payload["reward_mode"] == "promo"
    assert payload["entered_code"] is None
    assert payload["unresolved_code_reason"] is None
    assert payload["entered_code_matches"] == []
    assert payload["personal_discount"]["source_kind"] == "app_referral"
    assert _decimal(payload["personal_discount"]["estimated_discount_amount"]) == Decimal("6.00")
    assert payload["best_discount"]["source_kind"] == "app_referral"
    assert _decimal(payload["best_discount"]["estimated_discount_amount"]) == Decimal("6.00")
    assert len(payload["available_discount_options"]) == 1
    assert payload["available_discount_options"][0]["source_kind"] == "app_referral"
    assert _decimal(payload["available_discount_options"][0]["discount_percent"]) == Decimal("3.00")
    assert [option["source_kind"] for option in payload["stacked_discount_options"]] == ["app_referral"]


def test_benefit_check_does_not_offer_personal_discount_without_promo(
    client: TestClient,
    registered_user,
):
    _set_partner_program(
        registered_user["user_id"],
        purchase_total="200000.00",
        promo_code=None,
    )

    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"subtotal": "200.00", "currency": "RUB"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["personal_discount"] is None
    assert payload["reward_mode"] == "promo"
    assert payload["cashback_earned_points"] == 0
    assert payload["available_discount_options"] == []
    assert payload["stacked_discount_amount"] == "0.00"


def test_benefit_check_applies_personal_discount_to_discountable_subtotal_only(client: TestClient, registered_user):
    _set_partner_program(registered_user["user_id"])

    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"subtotal": "200.00", "discountable_subtotal": "100.00", "currency": "RUB", "reward_mode": "promo"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["entered_code_matches"] == []
    assert payload["reward_mode"] == "promo"
    assert _decimal(payload["stacked_discount_amount"]) == Decimal("3.00")
    assert _decimal(payload["total_after_discounts"]) == Decimal("197.00")


def test_benefit_check_rejects_unknown_entered_code_without_external_lookup(client: TestClient, registered_user):
    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"code": "Огонь26", "subtotal": "200.00", "discountable_subtotal": "100.00", "currency": "RUB"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["entered_code"] == "Огонь26"
    assert payload["entered_code_matches"] == []
    assert payload["unresolved_code_reason"] == "Промокод не найден или неактивен / Promo code was not found or is not active"
    assert payload["reward_mode"] == "cashback"
    assert payload["cashback_earned_points"] == 10
    assert _decimal(payload["stacked_discount_amount"]) == Decimal("0.00")
    assert _decimal(payload["total_after_discounts"]) == Decimal("200.00")
