import sys
import types
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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
from src.app.services.email_verification import EmailVerificationDeliveryError
from src.integrations.amocrm import amocrm_client
from src.database.models import Order, Product, User, Variant

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


def _delete_product(product_id: int) -> None:
    with Session(sync_engine) as session:
        product = session.get(Product, product_id)
        if product is None:
            return
        session.delete(product)
        session.commit()


def _create_product_variant(*, stock: int, price: Decimal) -> dict[str, int]:
    token = uuid.uuid4().hex
    with Session(sync_engine) as session:
        product = Product(
            sku=f"guest-sku-{token[:20]}",
            name=f"Guest Product {token[:12]}",
            description=None,
            usage=None,
            expiration=None,
            priority=0,
        )
        session.add(product)
        session.flush()

        variant = Variant(
            product_id=product.id,
            sku=f"guest-var-{token[:20]}",
            name=f"Guest Variant {token[:8]}",
            stock=stock,
            price=price,
        )
        session.add(variant)
        session.commit()
        session.refresh(product)
        session.refresh(variant)
        return {"product_id": product.id, "variant_id": variant.id}


def _get_user_by_email(email: str) -> User | None:
    with Session(sync_engine) as session:
        return session.execute(select(User).where(User.email == email)).scalar_one_or_none()


def _count_orders_for_user(user_id: int) -> int:
    with Session(sync_engine) as session:
        return len(list(session.execute(select(Order).where(Order.user_id == user_id)).scalars().all()))


def _build_pickup_payload() -> dict:
    return {
        "mode": "pickup",
        "provider": "CDEK",
        "country_code": "RU",
        "name": "СДЭК ПВЗ",
        "full_address": "Россия, Москва, ул. Пушкина, 10",
        "details": "Пн-Вс 10:00-20:00",
        "city": "Москва",
        "postal_code": "101000",
        "latitude": 55.751244,
        "longitude": 37.618423,
        "provider_reference": "MSK-PVZ-10",
        "delivery_calculation": {
            "delivery_sum": "199.00",
            "period_min": 2,
            "period_max": 4,
            "currency": "RUB",
        },
    }


def _build_guest_order_payload(*, variant_id: int, email: str, quantity: int = 2) -> dict:
    return {
        "items": [{"variant_id": variant_id, "quantity": quantity}],
        "delivery_address": _build_pickup_payload(),
        "recipient": {
            "name": "Иван",
            "surname": "Петров",
            "phone": "+79991234567",
            "email": email,
        },
        "payment_method": "later",
    }


@pytest.fixture()
def variant_factory():
    created_product_ids: list[int] = []

    def _factory(*, stock: int = 5, price: Decimal = Decimal("12.50")) -> dict[str, int]:
        payload = _create_product_variant(stock=stock, price=price)
        created_product_ids.append(payload["product_id"])
        return payload

    try:
        yield _factory
    finally:
        for product_id in reversed(created_product_ids):
            _delete_product(product_id)


@pytest.fixture()
def registered_user(register_verified_user):
    token = uuid.uuid4().hex[:12]
    payload = register_verified_user({
        "username": f"gexist_{token[:8]}",
        "email": f"guest_existing_{token}@example.com",
        "password": "test-password",
        "name": "Existing",
        "surname": "User",
    })
    user_id = payload["user"]["id"]

    try:
        yield {
            "user_id": user_id,
            "email": payload["user"]["email"],
            "headers": {"Authorization": f"Bearer {payload['access_token']}"},
        }
    finally:
        _delete_user(user_id)


@pytest.fixture()
def stub_amocrm(monkeypatch):
    class StubAmoCrmClient:
        STATUS_IDS = amocrm_client.STATUS_IDS
        STATUS_WORDS = amocrm_client.STATUS_WORDS

        async def find_lead_by_order_number(self, order_number):
            return None

        async def find_or_create_contact(self, **kwargs):
            return {"id": 12345}

        async def create_lead_with_contact_and_note(self, **kwargs):
            return {"id": 67890}

        async def update_lead_status(self, lead_id, status_id):
            return {"id": lead_id, "status_id": status_id}

    stub_client = StubAmoCrmClient()
    monkeypatch.setattr("src.app.services.guest_checkout.amocrm_client", stub_client)
    monkeypatch.setattr("src.app.services.orders.crm.amocrm_client", stub_client)


@pytest.fixture()
def sent_credentials_emails(monkeypatch):
    sent: list[dict[str, str]] = []

    async def fake_send_generated_account_credentials_email(*, to_email: str, username: str, password: str) -> None:
        sent.append({"to_email": to_email, "username": username, "password": password})

    monkeypatch.setattr(
        "src.app.modules.guest.router.send_generated_account_credentials_email",
        fake_send_generated_account_credentials_email,
    )
    return sent


def test_guest_basket_quote_returns_hydrated_totals_without_auth(client: TestClient, variant_factory):
    catalog = variant_factory(stock=5, price=Decimal("12.50"))

    response = client.post(
        "/api/v1/guest/basket/quote",
        json={"items": [{"variant_id": catalog["variant_id"], "quantity": 2}]},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user_id"] == 0
    assert payload["items"][0]["variant_id"] == catalog["variant_id"]
    assert payload["items"][0]["quantity"] == 2
    assert _decimal(payload["total_amount"]) == Decimal("25.00")
    assert _decimal(payload["grand_total"]) == Decimal("25.00")


def test_guest_order_creates_user_order_session_and_credentials_email(
    client: TestClient,
    variant_factory,
    stub_amocrm,
    sent_credentials_emails,
):
    catalog = variant_factory(stock=5, price=Decimal("19.00"))
    email = f"guest_order_{uuid.uuid4().hex[:12]}@example.com"

    response = client.post(
        "/api/v1/guest/orders",
        json=_build_guest_order_payload(variant_id=catalog["variant_id"], email=email),
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["session_id"] > 0
    assert payload["user"]["email"] == email
    assert payload["user"]["username"].startswith("guest")
    assert len(payload["user"]["username"]) <= 16
    assert payload["order"]["user_id"] == payload["user"]["id"]
    assert payload["order"]["recipient"]["email"] == email
    assert payload["credentials_email_sent"] is True
    assert sent_credentials_emails == [
        {
            "to_email": email,
            "username": payload["user"]["username"],
            "password": sent_credentials_emails[0]["password"],
        }
    ]
    assert sent_credentials_emails[0]["password"]

    _delete_user(payload["user"]["id"])


def test_guest_order_existing_email_returns_409_and_creates_no_order(
    client: TestClient,
    registered_user,
    variant_factory,
    stub_amocrm,
    sent_credentials_emails,
):
    catalog = variant_factory(stock=5, price=Decimal("19.00"))
    before_count = _count_orders_for_user(registered_user["user_id"])

    response = client.post(
        "/api/v1/guest/orders",
        json=_build_guest_order_payload(variant_id=catalog["variant_id"], email=registered_user["email"]),
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "email_exists"
    assert _count_orders_for_user(registered_user["user_id"]) == before_count
    assert sent_credentials_emails == []


def test_guest_order_email_failure_still_returns_order_and_auth(
    client: TestClient,
    variant_factory,
    stub_amocrm,
    monkeypatch,
):
    catalog = variant_factory(stock=5, price=Decimal("19.00"))
    email = f"guest_email_failure_{uuid.uuid4().hex[:12]}@example.com"

    async def fail_credentials_email(*, to_email: str, username: str, password: str) -> None:
        raise EmailVerificationDeliveryError("smtp unavailable")

    monkeypatch.setattr(
        "src.app.modules.guest.router.send_generated_account_credentials_email",
        fail_credentials_email,
    )

    response = client.post(
        "/api/v1/guest/orders",
        json=_build_guest_order_payload(variant_id=catalog["variant_id"], email=email),
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["access_token"]
    assert payload["order"]["recipient"]["email"] == email
    assert payload["credentials_email_sent"] is False
    assert payload["credentials_email_error"]

    _delete_user(payload["user"]["id"])


def test_personal_data_update_changes_account_fields_and_rejects_duplicates(
    client: TestClient,
    registered_user,
    register_verified_user,
):
    token = uuid.uuid4().hex[:12]
    duplicate_payload = register_verified_user({
        "username": f"gdup_{token[:8]}",
        "email": f"guest_duplicate_{token}@example.com",
        "password": "test-password",
        "name": "Duplicate",
        "surname": "User",
    })
    duplicate_user_id = duplicate_payload["user"]["id"]
    headers = registered_user["headers"]

    try:
        update_response = client.patch(
            "/api/v1/users/me/profile/personal-data",
            headers=headers,
            json={
                "username": f"guest_updated_{token}",
                "username": f"gupd_{token[:8]}",
                "email": f"guest_updated_{token}@example.com",
                "name": "Updated",
                "surname": "Customer",
                "phone_number": "+79990001122",
                "password": "new-test-password",
            },
        )
        assert update_response.status_code == 200, update_response.text
        updated = update_response.json()
        assert updated["username"] == f"gupd_{token[:8]}"
        assert updated["email"] == f"guest_updated_{token}@example.com"
        assert updated["name"] == "Updated"
        assert updated["surname"] == "Customer"
        assert updated["phone_number"] == "+79990001122"

        duplicate_username_response = client.patch(
            "/api/v1/users/me/profile/personal-data",
            headers=headers,
            json={"username": duplicate_payload["user"]["username"]},
        )
        assert duplicate_username_response.status_code == 409, duplicate_username_response.text

        duplicate_email_response = client.patch(
            "/api/v1/users/me/profile/personal-data",
            headers=headers,
            json={"email": duplicate_payload["user"]["email"]},
        )
        assert duplicate_email_response.status_code == 409, duplicate_email_response.text
    finally:
        _delete_user(duplicate_user_id)
