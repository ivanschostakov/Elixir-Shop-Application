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
from src.integrations.website_identity import website_identity_client
from src.database.models import AppPromo, OrderBenefitApplication, User, WebsiteIdentity

SYNC_DB_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
sync_engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)


def _decimal(value) -> Decimal:
    return Decimal(str(value))


def _delete_user(user_id: int) -> None:
    with Session(sync_engine) as session:
        user = session.get(User, user_id)
        if user is None:
            return
        website_identity = session.query(WebsiteIdentity).filter(WebsiteIdentity.user_id == user_id).one_or_none()
        if website_identity is not None:
            session.delete(website_identity)
            session.flush()
        session.delete(user)
        session.commit()


def _delete_app_promo(app_promo_id: int) -> None:
    with Session(sync_engine) as session:
        app_promo = session.get(AppPromo, app_promo_id)
        if app_promo is None:
            return
        session.delete(app_promo)
        session.commit()


def _delete_order_benefit_application(application_id: int) -> None:
    with Session(sync_engine) as session:
        application = session.get(OrderBenefitApplication, application_id)
        if application is None:
            return
        session.delete(application)
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


@pytest.fixture()
def app_promo_factory():
    created_promo_ids: list[int] = []

    def _factory(
        *,
        code: str,
        name: str,
        benefit_kind: str,
        discount_percent: Decimal | None = None,
        discount_amount: Decimal | None = None,
        currency: str | None = None,
        is_active: bool = True,
        max_total_uses: int | None = None,
        max_uses_per_user: int | None = None,
    ) -> AppPromo:
        with Session(sync_engine) as session:
            app_promo = AppPromo(
                code=code,
                name=name,
                source_kind="app",
                benefit_kind=benefit_kind,
                discount_percent=discount_percent,
                discount_amount=discount_amount,
                currency=currency,
                is_active=is_active,
                max_total_uses=max_total_uses,
                max_uses_per_user=max_uses_per_user,
                stacking_policy="exclusive",
            )
            session.add(app_promo)
            session.commit()
            session.refresh(app_promo)
            session.expunge(app_promo)
            created_promo_ids.append(app_promo.id)
            return app_promo

    try:
        yield _factory
    finally:
        for promo_id in reversed(created_promo_ids):
            _delete_app_promo(promo_id)


@pytest.fixture()
def benefit_application_factory():
    created_application_ids: list[int] = []

    def _factory(*, order_id: int, user_id: int, app_promo_id: int, code: str, status: str = "applied") -> int:
        with Session(sync_engine) as session:
            application = OrderBenefitApplication(
                order_id=order_id,
                user_id=user_id,
                source_kind="app_promo",
                app_promo_id=app_promo_id,
                entered_code=code,
                resolved_code=code,
                currency="RUB",
                status=status,
            )
            session.add(application)
            session.commit()
            session.refresh(application)
            created_application_ids.append(application.id)
            return application.id

    try:
        yield _factory
    finally:
        for application_id in reversed(created_application_ids):
            _delete_order_benefit_application(application_id)


def _website_payload(*, website_user_id: int, login: str, email: str) -> dict:
    return {
        "user": {
            "id": website_user_id,
            "login": login,
            "name": "Website",
            "last_name": "Customer",
            "email": email,
            "personal_phone": "+79990000001",
            "personal_mobile": "+79990000002",
            "personal_city": "Ufa",
            "date_register": "2026-04-01T12:00:00+05:00",
            "last_login": "2026-04-08T20:15:00+05:00",
            "group_ids": [3, 33],
            "group_names": ["Website Customers", "Заказы больше 100 т. р."],
            "custom_fields": {
                "UF_PROMO": "WELCOME",
                "UF_PARENT_ID": "7",
                "UF_PERCENT": "19",
                "UF_ORDER_SUMM": "3060.33|RUB",
            },
        },
        "discounts": {
            "referral_program": {
                "promo_code": "WELCOME",
                "parent_user_id": 7,
                "percent": 19,
                "order_sum": {"raw": "3060.33|RUB", "amount": 3060.33, "currency": "RUB"},
            },
            "referral_tier": {"group_id": 33, "group_name": "Заказы больше 100 т. р."},
            "bonus_account": {
                "id": website_user_id,
                "user_id": website_user_id,
                "balance": 125.5,
                "currency": "RUB",
                "active": True,
                "date_create": "2026-04-01T12:00:00+05:00",
            },
            "personal_discounts": [
                {
                    "id": 7,
                    "source_kind": "group",
                    "name": "VIP",
                    "discount_type": "percent",
                    "discount_value": 5.0,
                    "currency": "RUB",
                    "priority": 10,
                    "is_stackable": False,
                    "is_active": True,
                }
            ],
            "discount_groups": [{"id": 33, "name": "Заказы больше 100 т. р."}],
            "active_coupons": [
                {
                    "id": website_user_id + 5000,
                    "coupon": "APRIL-10",
                    "max_use": 1,
                    "use_count": 0,
                    "discount": {
                        "id": 901,
                        "name": "April 10%",
                        "discount_type": "percent",
                        "discount_value": 10.0,
                        "value": 10.0,
                        "currency": "RUB",
                    },
                }
            ],
            "recent_used_coupons": [],
        },
    }


def _link_website_identity(client: TestClient, registered_user, monkeypatch: pytest.MonkeyPatch, *, website_user_id: int) -> None:
    website_data = _website_payload(
        website_user_id=website_user_id, login=f"website-{website_user_id}", email=f"linked_{uuid.uuid4().hex[:8]}@example.com"
    )

    async def fake_authenticate(*, login: str, password: str) -> dict:
        assert login == "site-login"
        assert password == "site-password"
        return website_data

    monkeypatch.setattr(website_identity_client, "authenticate", fake_authenticate)

    response = client.post(
        "/api/v1/users/me/website-identity/link",
        headers=registered_user["headers"],
        json={"login": "site-login", "password": "site-password"},
    )
    assert response.status_code == 200, response.text


def test_benefit_check_returns_website_coupon_personal_discount_and_bonus(
    client: TestClient, registered_user, monkeypatch: pytest.MonkeyPatch
):
    _link_website_identity(client, registered_user, monkeypatch, website_user_id=92000 + (uuid.uuid4().int % 1000000))

    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"code": "  APRIL-10  ", "subtotal": "200.00", "currency": "RUB", "requested_bonus_amount": "50.00"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["website_identity_id"] is not None
    assert payload["subtotal_source"] == "request"
    assert _decimal(payload["basket_subtotal"]) == Decimal("200.00")
    assert payload["entered_code"] == "APRIL-10"
    assert payload["unresolved_code_reason"] is None
    assert len(payload["entered_code_matches"]) == 1
    assert payload["entered_code_matches"][0]["source_kind"] == "website_coupon"
    assert payload["entered_code_matches"][0]["is_applicable"] is True
    assert _decimal(payload["entered_code_matches"][0]["estimated_discount_amount"]) == Decimal("20.00")
    assert payload["personal_discount"]["source_kind"] == "app_referral"
    assert _decimal(payload["personal_discount"]["estimated_discount_amount"]) == Decimal("38.00")
    assert payload["best_discount"]["source_kind"] == "app_referral"
    assert _decimal(payload["best_discount"]["estimated_discount_amount"]) == Decimal("38.00")
    assert len(payload["available_discount_options"]) == 3
    assert payload["available_discount_options"][0]["source_kind"] == "app_referral"
    assert _decimal(payload["available_discount_options"][0]["discount_percent"]) == Decimal("19.00")
    assert [option["source_kind"] for option in payload["stacked_discount_options"]] == [
        "app_referral",
        "website_discount_entitlement",
        "website_coupon",
    ]
    assert payload["bonus_option"]["is_available"] is True
    assert _decimal(payload["bonus_option"]["max_applicable_amount"]) == Decimal("125.50")
    assert _decimal(payload["bonus_option"]["applicable_amount"]) == Decimal("50.00")
    assert _decimal(payload["bonus_option"]["estimated_total_after_bonus"]) == Decimal("150.00")


def test_benefit_check_matches_active_app_promo(client: TestClient, registered_user, app_promo_factory):
    app_promo_factory(code="APP20", name="App Twenty", benefit_kind="percent", discount_percent=Decimal("20.00"))

    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"code": "app20", "subtotal": "150.00", "currency": "RUB"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["website_identity_id"] is None
    assert payload["unresolved_code_reason"] is None
    assert len(payload["entered_code_matches"]) == 1
    assert payload["entered_code_matches"][0]["source_kind"] == "app_promo"
    assert payload["entered_code_matches"][0]["status"] == "available"
    assert _decimal(payload["entered_code_matches"][0]["estimated_discount_amount"]) == Decimal("30.00")
    assert payload["best_discount"]["source_kind"] == "app_promo"
    assert _decimal(payload["best_discount"]["estimated_discount_amount"]) == Decimal("30.00")
    assert payload["bonus_option"] is None


def test_benefit_check_rejects_app_promo_when_user_limit_is_reached(
    client: TestClient, registered_user, app_promo_factory, benefit_application_factory
):
    app_promo = app_promo_factory(
        code="LIMIT1", name="Limited Once", benefit_kind="percent", discount_percent=Decimal("15.00"), max_uses_per_user=1
    )
    benefit_application_factory(
        order_id=700000 + (uuid.uuid4().int % 100000), user_id=registered_user["user_id"], app_promo_id=app_promo.id, code="LIMIT1"
    )

    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"code": "LIMIT1", "subtotal": "100.00", "currency": "RUB"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["entered_code_matches"]) == 1
    assert payload["entered_code_matches"][0]["source_kind"] == "app_promo"
    assert payload["entered_code_matches"][0]["status"] == "usage_limit_reached"
    assert payload["entered_code_matches"][0]["is_applicable"] is False
    assert payload["available_discount_options"] == []
    assert payload["best_discount"] is None


def test_benefit_check_marks_coupon_unsupported_without_explicit_discount_mode(
    client: TestClient, registered_user, monkeypatch: pytest.MonkeyPatch
):
    website_user_id = 92000 + (uuid.uuid4().int % 1000000)
    website_data = _website_payload(
        website_user_id=website_user_id, login=f"website-{website_user_id}", email=f"linked_{uuid.uuid4().hex[:8]}@example.com"
    )
    website_data["discounts"]["active_coupons"] = [
        {
            "id": website_user_id + 7000,
            "coupon": "STRICT-10",
            "type": 1,
            "max_use": 1,
            "use_count": 0,
            "discount": {"id": 902, "name": "Strict 10", "value": 10.0},
        }
    ]
    website_data["discounts"]["personal_discounts"] = []
    website_data["discounts"]["discount_groups"] = []

    async def fake_authenticate(*, login: str, password: str) -> dict:
        assert login == "site-login"
        assert password == "site-password"
        return website_data

    monkeypatch.setattr(website_identity_client, "authenticate", fake_authenticate)

    link_response = client.post(
        "/api/v1/users/me/website-identity/link",
        headers=registered_user["headers"],
        json={"login": "site-login", "password": "site-password"},
    )
    assert link_response.status_code == 200, link_response.text

    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"code": "STRICT-10", "subtotal": "200.00", "currency": "RUB"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["entered_code_matches"]) == 1
    assert payload["entered_code_matches"][0]["source_kind"] == "website_coupon"
    assert payload["entered_code_matches"][0]["status"] == "unsupported"
    assert payload["entered_code_matches"][0]["is_applicable"] is False
    assert payload["best_discount"]["source_kind"] == "app_referral"
    assert _decimal(payload["best_discount"]["discount_percent"]) == Decimal("19.00")


def test_benefit_check_parses_legacy_serialized_coupon_discount(
    client: TestClient, registered_user, monkeypatch: pytest.MonkeyPatch
):
    website_user_id = 92000 + (uuid.uuid4().int % 1000000)
    website_data = _website_payload(
        website_user_id=website_user_id, login=f"website-{website_user_id}", email=f"linked_{uuid.uuid4().hex[:8]}@example.com"
    )
    website_data["discounts"]["personal_discounts"] = []
    website_data["discounts"]["active_coupons"] = [
        {
            "id": website_user_id + 7100,
            "coupon": "LEGACY-3",
            "type": 4,
            "max_use": 1,
            "use_count": 0,
            "description": "Персональный промо-код пользователя",
            "discount": {
                "id": 903,
                "name": "Legacy 3%",
                "short_description": 'a:4:{s:4:"TYPE";s:8:"Discount";s:5:"VALUE";d:3;s:11:"LIMIT_VALUE";i:0;s:10:"VALUE_TYPE";s:1:"P";}',
                "value": 0,
                "currency": "RUB",
            },
        }
    ]

    async def fake_authenticate(*, login: str, password: str) -> dict:
        assert login == "site-login"
        assert password == "site-password"
        return website_data

    monkeypatch.setattr(website_identity_client, "authenticate", fake_authenticate)

    link_response = client.post(
        "/api/v1/users/me/website-identity/link",
        headers=registered_user["headers"],
        json={"login": "site-login", "password": "site-password"},
    )
    assert link_response.status_code == 200, link_response.text

    response = client.post(
        "/api/v1/users/me/benefits/check",
        headers=registered_user["headers"],
        json={"code": "LEGACY-3", "subtotal": "200.00", "currency": "RUB"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["entered_code_matches"]) == 1
    assert payload["entered_code_matches"][0]["source_kind"] == "website_coupon"
    assert payload["entered_code_matches"][0]["status"] == "available"
    assert payload["entered_code_matches"][0]["is_applicable"] is True
    assert _decimal(payload["entered_code_matches"][0]["estimated_discount_amount"]) == Decimal("6.00")
    assert payload["best_discount"]["source_kind"] == "app_referral"
    assert [option["source_kind"] for option in payload["stacked_discount_options"]] == ["app_referral", "website_coupon"]
