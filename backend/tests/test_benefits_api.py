import asyncio
import sys
import types
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

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
from src.app.modules.users.me import benefits as benefits_module
from src.app.modules.users.me.schemas.benefits import BenefitCheckPayload
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


def _set_bonus_program_with_promo(
    user_id: int,
    *,
    purchase_total: str = "0.00",
    promo_code: str = "REFERRER",
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
        profile.reward_program = "bonus"
        profile.reward_program_selection_source = "system_default"
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


def test_entering_promo_replaces_cashback_with_growing_discount(
    client: TestClient,
    registered_user,
):
    _set_bonus_program_with_promo(
        registered_user["user_id"],
        purchase_total="75000.00",
    )

    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"subtotal": "200.00", "currency": "RUB"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["reward_program"] == "partner"
    assert payload["reward_mode"] == "promo"
    assert _decimal(payload["personal_discount"]["discount_percent"]) == Decimal("7.00")
    assert _decimal(payload["stacked_discount_amount"]) == Decimal("14.00")
    assert _decimal(payload["total_after_discounts"]) == Decimal("186.00")
    assert payload["cashback_earned_points"] == 0


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
    assert payload["reward_mode"] == "promo"
    assert payload["cashback_earned_points"] == 10
    assert _decimal(payload["stacked_discount_amount"]) == Decimal("0.00")
    assert _decimal(payload["total_after_discounts"]) == Decimal("200.00")


def test_benefit_check_uses_owned_order_draft_context(monkeypatch):
    draft_items = [
        SimpleNamespace(
            product_id=11,
            variant_id=17,
            quantity=2,
            line_total=Decimal("200.00"),
        )
    ]
    draft = SimpleNamespace(
        basket_subtotal=Decimal("200.00"),
        currency="RUB",
        items=draft_items,
    )
    quote_items = [
        {
            "product_system_id": "product-system-id",
            "variant_system_id": "variant-system-id",
            "quantity": 2,
        }
    ]
    captured: dict = {}

    async def fake_get_order_draft(_db, draft_id: int, *, user_id: int):
        assert draft_id == 42
        assert user_id == 7
        return draft

    async def fake_discountable_subtotal(_db, lines):
        assert list(lines) == [(11, Decimal("200.00"))]
        return Decimal("200.00")

    async def fake_build_quote_items(_db, items):
        assert items is draft_items
        return quote_items

    async def fake_resolve(_db, **kwargs):
        captured.update(kwargs)
        return {
            "subtotal_source": "request",
            "basket_subtotal": kwargs["subtotal"],
            "currency": kwargs["currency"],
            "stacked_discount_amount": Decimal("6.00"),
            "total_after_discounts": Decimal("194.00"),
        }

    class FakeDB:
        committed = False

        async def commit(self):
            self.committed = True

    monkeypatch.setattr(benefits_module, "get_order_draft_by_id", fake_get_order_draft)
    monkeypatch.setattr(benefits_module, "discountable_subtotal_for_lines", fake_discountable_subtotal)
    monkeypatch.setattr(benefits_module, "build_bitrix_delivery_items", fake_build_quote_items)
    monkeypatch.setattr(benefits_module, "resolve_benefits_for_user", fake_resolve)

    db = FakeDB()
    result = asyncio.run(
        benefits_module.check_my_benefits(
            payload=BenefitCheckPayload(
                draft_id=42,
                code="ROMANI",
                subtotal=Decimal("1.00"),
                discountable_subtotal=Decimal("1.00"),
                currency="USD",
            ),
            db=db,
            current_user=SimpleNamespace(id=7),
        )
    )

    assert result.basket_subtotal == Decimal("200.00")
    assert result.currency == "RUB"
    assert result.stacked_discount_amount == Decimal("6.00")
    assert captured["entered_code"] == "ROMANI"
    assert captured["subtotal"] == Decimal("200.00")
    assert captured["discountable_subtotal"] == Decimal("200.00")
    assert captured["currency"] == "RUB"
    assert captured["quote_items"] is quote_items
    assert db.committed is True
