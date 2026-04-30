import sys
import types
import uuid
import pytest

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

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
from src.integrations.amocrm import amocrm_client
from src.database.models import Order, Product, User, UserPushToken, Variant

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
            sku=f"order-sku-{token[:20]}",
            name=f"Order Product {token[:12]}",
            description=None,
            usage=None,
            expiration=None,
            priority=0,
        )
        session.add(product)
        session.flush()

        variant = Variant(
            product_id=product.id,
            sku=f"order-var-{token[:20]}",
            name=f"Order Variant {token[:8]}",
            stock=stock,
            price=price,
        )
        session.add(variant)
        session.commit()
        session.refresh(product)
        session.refresh(variant)
        return {"product_id": product.id, "variant_id": variant.id}


def _get_order(order_id: int) -> Order:
    with Session(sync_engine) as session:
        order = session.get(Order, order_id)
        assert order is not None
        return order


def _update_order(order_id: int, **fields) -> None:
    with Session(sync_engine) as session:
        order = session.get(Order, order_id)
        assert order is not None
        for field, value in fields.items():
            setattr(order, field, value)
        session.commit()


def _get_push_tokens_for_user(user_id: int) -> list[str]:
    with Session(sync_engine) as session:
        stmt = select(UserPushToken.expo_push_token).where(UserPushToken.user_id == user_id).order_by(UserPushToken.id.asc())
        return list(session.execute(stmt).scalars().all())


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


def _create_ready_draft(client: TestClient, headers: dict[str, str], variant_id: int) -> dict:
    basket_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=headers,
        json={"variant_id": variant_id, "quantity": 2},
    )
    assert basket_response.status_code == 200, basket_response.text

    draft_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=headers,
        json=_build_pickup_payload(),
    )
    assert draft_response.status_code == 201, draft_response.text
    draft = draft_response.json()

    recipient_response = client.patch(
        f"/api/v1/users/me/order-drafts/{draft['id']}",
        headers=headers,
        json={
            "new_recipient": {
                "name": "Иван",
                "surname": "Петров",
                "phone": "+79991234567",
                "email": "ivan.petrov@example.com",
            }
        },
    )
    assert recipient_response.status_code == 200, recipient_response.text
    return recipient_response.json()


def _create_order_for_history(
    client: TestClient,
    headers: dict[str, str],
    variant_id: int,
    *,
    payment_method: str = "later",
) -> dict:
    draft = _create_ready_draft(client, headers, variant_id)
    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=headers,
        json={"draft_id": draft["id"], "payment_method": payment_method},
    )
    assert order_response.status_code == 200, order_response.text
    return order_response.json()


@pytest.fixture()
def registered_user(register_verified_user):
    token = uuid.uuid4().hex[:12]
    payload = register_verified_user({
        "username": f"u{token}",
        "email": f"orders_{token}@example.com",
        "password": "test-password",
        "name": "Orders",
        "surname": "Tester",
    })
    user_id = payload["user"]["id"]
    email = payload["user"]["email"]

    try:
        yield {
            "user_id": user_id,
            "email": email,
            "headers": {"Authorization": f"Bearer {payload['access_token']}"},
        }
    finally:
        _delete_user(user_id)


@pytest.fixture()
def second_registered_user(register_verified_user):
    token = uuid.uuid4().hex[:12]
    payload = register_verified_user({
        "username": f"u{token}",
        "email": f"orders_second_{token}@example.com",
        "password": "test-password",
        "name": "Orders",
        "surname": "Second",
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
def stub_amocrm(monkeypatch):
    calls = {"status_updates": []}

    async def fake_find_lead_by_order_number(order_number):
        return None

    async def fake_find_or_create_contact(**kwargs):
        return {"id": 12345}

    async def fake_create_lead_with_contact_and_note(**kwargs):
        return {"id": 67890}

    async def fake_update_lead_status(lead_id, status_id):
        calls["status_updates"].append({"lead_id": lead_id, "status_id": status_id})
        return {"id": lead_id, "status_id": status_id}

    monkeypatch.setattr("src.app.services.orders.amocrm_client.find_lead_by_order_number", fake_find_lead_by_order_number)
    monkeypatch.setattr("src.app.services.orders.amocrm_client.find_or_create_contact", fake_find_or_create_contact)
    monkeypatch.setattr("src.app.services.orders.amocrm_client.create_lead_with_contact_and_note", fake_create_lead_with_contact_and_note)
    monkeypatch.setattr("src.app.services.orders.amocrm_client.update_lead_status", fake_update_lead_status)
    yield calls


def test_create_final_order_uses_self_recipient_when_draft_recipient_is_missing(client: TestClient, registered_user, variant_factory, stub_amocrm):
    catalog = variant_factory(stock=5, price=Decimal("12.50"))

    basket_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": catalog["variant_id"], "quantity": 1},
    )
    assert basket_response.status_code == 200, basket_response.text

    draft_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert draft_response.status_code == 201, draft_response.text
    draft = draft_response.json()

    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "later"},
    )

    assert order_response.status_code == 200, order_response.text
    payload = order_response.json()
    assert payload["recipient"]["name"] == "Orders"
    assert payload["recipient"]["surname"] == "Tester"
    assert payload["recipient"]["email"] == registered_user["email"]


def test_create_final_order_persists_snapshot_and_amocrm_link(client: TestClient, registered_user, variant_factory, stub_amocrm):
    catalog = variant_factory(stock=5, price=Decimal("19.00"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])

    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "sbp"},
    )

    assert order_response.status_code == 200, order_response.text
    payload = order_response.json()
    assert payload["draft_id"] is None
    assert payload["payment_method"] == "sbp"
    assert payload["payment_status"] == "draft"
    assert payload["amocrm_lead_id"] == 67890
    assert payload["selected_delivery_service"] == "CDEK"
    assert payload["selected_delivery_payload"]["deliveryMode"] == "office"
    assert payload["checkout_snapshot"]["contact_info"]["email"] == "ivan.petrov@example.com"
    assert payload["checkout_snapshot"]["checkout_data"]["items"][0]["featureId"] == catalog["variant_id"]
    assert payload["checkout_snapshot"]["payment_method"] == "sbp"

    stored_order = _get_order(payload["id"])
    assert stored_order.amocrm_lead_id == 67890
    assert stored_order.selected_delivery_service == "CDEK"
    assert stored_order.draft_id is None


def test_create_final_order_removes_source_draft(client: TestClient, registered_user, variant_factory, stub_amocrm):
    catalog = variant_factory(stock=5, price=Decimal("19.00"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])

    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "sbp"},
    )

    assert order_response.status_code == 200, order_response.text

    draft_response = client.get(
        f"/api/v1/users/me/order-drafts/{draft['id']}",
        headers=registered_user["headers"],
    )

    assert draft_response.status_code == 404, draft_response.text


def test_create_payment_later_marks_order_pending(client: TestClient, registered_user, variant_factory, stub_amocrm):
    catalog = variant_factory(stock=5, price=Decimal("15.00"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])

    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "later"},
    )
    assert order_response.status_code == 200, order_response.text
    order_id = order_response.json()["id"]

    payment_response = client.post(
        "/api/v1/payments/create",
        headers=registered_user["headers"],
        json={"order_id": order_id},
    )

    assert payment_response.status_code == 200, payment_response.text
    payload = payment_response.json()
    assert payload["order_id"] == order_id
    assert payload["payment_method"] == "later"
    assert payload["payment_status"] == "pending"

    stored_order = _get_order(order_id)
    assert stored_order.payment_provider == "manager"
    assert stored_order.payment_status == "pending"


def test_create_payment_sbp_returns_qr_payload(client: TestClient, registered_user, variant_factory, stub_amocrm, monkeypatch):
    catalog = variant_factory(stock=5, price=Decimal("25.00"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])

    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "sbp"},
    )
    assert order_response.status_code == 200, order_response.text
    order_id = order_response.json()["id"]

    async def fake_create_invoice(**kwargs):
        return {"Result": {"InvoiceId": "invoice-1"}}

    async def fake_sbp_payment(**kwargs):
        return {
            "Result": {
                "PaymentStep": "Created",
                "Form3DS": '{"SbpQrCodeUrl":"https://example.com/qr","SbpQrCodeImage":"https://example.com/qr.png"}',
            }
        }

    async def fake_get_bank_card_payment_state(**kwargs):
        return {
            "Result": {
                "PaymentStep": "Created",
                "Form3DS": '{"SbpQrCodeUrl":"https://example.com/qr","SbpQrCodeImage":"https://example.com/qr.png"}',
            }
        }

    async def fake_resolve_payment_qr_image(*args, **kwargs):
        return "https://api.example.test/media/orders/1/qr-1.png"

    monkeypatch.setattr("src.app.services.orders.intellectmoney.create_invoice", fake_create_invoice)
    monkeypatch.setattr("src.app.services.orders.intellectmoney.sbp_payment", fake_sbp_payment)
    monkeypatch.setattr("src.app.services.orders.intellectmoney.get_bank_card_payment_state", fake_get_bank_card_payment_state)
    monkeypatch.setattr("src.app.services.orders._resolve_payment_qr_image", fake_resolve_payment_qr_image)

    payment_response = client.post(
        "/api/v1/payments/create",
        headers=registered_user["headers"],
        json={"order_id": order_id},
    )

    assert payment_response.status_code == 200, payment_response.text
    payload = payment_response.json()
    assert payload["order_id"] == order_id
    assert payload["invoice_id"] == "invoice-1"
    assert payload["qr_url"] == "https://example.com/qr"
    assert payload["qr_image"] == "https://api.example.test/media/orders/1/qr-1.png"
    assert payload["payment_status"] == "pending"
    assert stub_amocrm["status_updates"][-1] == {
        "lead_id": 67890,
        "status_id": amocrm_client.STATUS_IDS["pending_payment"],
    }

    stored_order = _get_order(order_id)
    assert stored_order.payment_provider == "intellectmoney"
    assert stored_order.payment_invoice_id == "invoice-1"


def test_create_payment_sbp_error_keeps_order_retryable(client: TestClient, registered_user, variant_factory, stub_amocrm, monkeypatch):
    catalog = variant_factory(stock=5, price=Decimal("25.00"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])

    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "sbp"},
    )
    assert order_response.status_code == 200, order_response.text
    order_id = order_response.json()["id"]

    async def fake_create_invoice(**kwargs):
        return {"Result": {"InvoiceId": "invoice-error-1"}}

    async def fake_sbp_payment(**kwargs):
        return {"Result": {"State": {"Code": 0, "Desc": "Успешно обработан"}}}

    async def fake_get_bank_card_payment_state(**kwargs):
        return {
            "Result": {
                "PaymentStep": "Error",
                "Message": "Операция просрочена",
                "State": {"Code": 0, "Desc": "Успешно обработан"},
            }
        }

    async def fake_resolve_payment_qr_image(*args, **kwargs):
        return None

    monkeypatch.setattr("src.app.services.orders.intellectmoney.create_invoice", fake_create_invoice)
    monkeypatch.setattr("src.app.services.orders.intellectmoney.sbp_payment", fake_sbp_payment)
    monkeypatch.setattr("src.app.services.orders.intellectmoney.get_bank_card_payment_state", fake_get_bank_card_payment_state)
    monkeypatch.setattr("src.app.services.orders._resolve_payment_qr_image", fake_resolve_payment_qr_image)

    payment_response = client.post(
        "/api/v1/payments/create",
        headers=registered_user["headers"],
        json={"order_id": order_id},
    )

    assert payment_response.status_code == 200, payment_response.text
    payload = payment_response.json()
    assert payload["payment_status"] == "error"
    assert payload["can_retry"] is True
    assert stub_amocrm["status_updates"][-1] == {
        "lead_id": 67890,
        "status_id": amocrm_client.STATUS_IDS["waiting_response"],
    }

    stored_order = _get_order(order_id)
    assert stored_order.payment_status == "error"
    assert stored_order.is_active is True
    assert stored_order.is_canceled is False


def test_amocrm_paid_webhook_creates_delivery_once(client: TestClient, registered_user, variant_factory, stub_amocrm, monkeypatch):
    catalog = variant_factory(stock=5, price=Decimal("17.00"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])

    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "later"},
    )
    assert order_response.status_code == 200, order_response.text
    order_id = order_response.json()["id"]
    order_number = order_response.json()["order_number"]

    calls = {"count": 0}

    async def fake_get_lead(lead_id):
        return {
            "id": lead_id,
            "name": f"Заказ №{order_number} с Приложения",
            "status_id": amocrm_client.STATUS_IDS["check_paid"],
            "pipeline_id": amocrm_client.PIPELINE_ID,
        }

    async def fake_create_delivery_for_order(order):
        calls["count"] += 1
        return {"delivery_provider_ref": "delivery-ref-1"}

    monkeypatch.setattr("src.app.modules.webhooks.router.amocrm_client.get_lead", fake_get_lead)
    monkeypatch.setattr("src.app.services.orders.create_delivery_for_order", fake_create_delivery_for_order)

    webhook_body = (
        f"leads[status][0][id]=67890&"
        f"leads[status][0][status_id]={amocrm_client.STATUS_IDS['check_paid']}&"
        f"leads[status][0][pipeline_id]={amocrm_client.PIPELINE_ID}"
    )

    first_response = client.post(
        "/api/v1/webhooks/amocrm",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        content=webhook_body,
    )
    assert first_response.status_code == 200, first_response.text

    second_response = client.post(
        "/api/v1/webhooks/amocrm",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        content=webhook_body,
    )
    assert second_response.status_code == 200, second_response.text

    stored_order = _get_order(order_id)
    assert stored_order.delivery_provider_ref == "delivery-ref-1"
    assert stored_order.delivery_created_at is not None
    assert calls["count"] == 1


@pytest.mark.parametrize(
    ("payment_status_code", "expected_payment_status", "expected_amocrm_status_id", "expected_is_active", "expected_is_canceled"),
    [
        (4, "canceled", amocrm_client.STATUS_IDS["canceled"], False, True),
        (6, "hold", amocrm_client.STATUS_IDS["waiting_response"], True, False),
        (8, "refunded", amocrm_client.STATUS_IDS["refund_declined"], False, True),
    ],
)
def test_intellectmoney_webhook_updates_amocrm_status_for_non_paid_results(
    client: TestClient,
    registered_user,
    variant_factory,
    stub_amocrm,
    monkeypatch,
    payment_status_code: int,
    expected_payment_status: str,
    expected_amocrm_status_id: int,
    expected_is_active: bool,
    expected_is_canceled: bool,
):
    catalog = variant_factory(stock=5, price=Decimal("21.00"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])

    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "sbp"},
    )
    assert order_response.status_code == 200, order_response.text
    order_id = order_response.json()["id"]
    order_number = order_response.json()["order_number"]

    monkeypatch.setattr("src.app.modules.webhooks.router.intellectmoney.verify_webhook_hash", lambda payload: True)

    webhook_response = client.post(
        "/api/v1/webhooks/intellectmoney",
        data={
            "EshopId": "shop-id",
            "OrderId": order_number,
            "ServiceName": f"Заказ №{order_number}",
            "EshopAccount": "",
            "RecipientAmount": "21.00",
            "RecipientCurrency": "RUB",
            "PaymentStatus": str(payment_status_code),
            "UserName": "Иван Петров",
            "UserEmail": "ivan.petrov@example.com",
            "PaymentData": "2026-04-23 12:00:00",
            "PaymentId": f"invoice-{payment_status_code}",
            "Hash": "ok",
        },
    )

    assert webhook_response.status_code == 200, webhook_response.text
    assert stub_amocrm["status_updates"][-1] == {
        "lead_id": 67890,
        "status_id": expected_amocrm_status_id,
    }

    stored_order = _get_order(order_id)
    assert stored_order.payment_provider == "intellectmoney"
    assert stored_order.payment_invoice_id == f"invoice-{payment_status_code}"
    assert stored_order.payment_status == expected_payment_status
    assert stored_order.status == amocrm_client.STATUS_WORDS[expected_amocrm_status_id]
    assert stored_order.is_active is expected_is_active
    assert stored_order.is_canceled is expected_is_canceled


def test_list_orders_supports_history_filters_and_history_fields(
    client: TestClient,
    registered_user,
    second_registered_user,
    variant_factory,
    stub_amocrm,
):
    created_order = _create_order_for_history(client, registered_user["headers"], variant_factory()["variant_id"])
    sent_order = _create_order_for_history(client, registered_user["headers"], variant_factory()["variant_id"])
    delivered_order = _create_order_for_history(client, registered_user["headers"], variant_factory()["variant_id"])
    unknown_order = _create_order_for_history(client, registered_user["headers"], variant_factory()["variant_id"])
    other_user_order = _create_order_for_history(client, second_registered_user["headers"], variant_factory()["variant_id"])

    _update_order(
        created_order["id"],
        created_at=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc),
        status=amocrm_client.STATUS_WORDS[amocrm_client.STATUS_IDS["main"]],
        is_active=True,
        is_paid=False,
        is_canceled=False,
        is_shipped=False,
    )
    _update_order(
        sent_order["id"],
        created_at=datetime(2026, 4, 11, 9, 0, tzinfo=timezone.utc),
        status=amocrm_client.STATUS_WORDS[amocrm_client.STATUS_IDS["package_sent"]],
        is_active=True,
        is_paid=True,
        is_canceled=False,
        is_shipped=True,
    )
    _update_order(
        delivered_order["id"],
        created_at=datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc),
        status=amocrm_client.STATUS_WORDS[amocrm_client.STATUS_IDS["package_delivered"]],
        is_active=True,
        is_paid=True,
        is_canceled=False,
        is_shipped=True,
    )
    _update_order(
        unknown_order["id"],
        created_at=datetime(2026, 4, 13, 9, 0, tzinfo=timezone.utc),
        status="Нестандартный этап",
        is_active=False,
        is_paid=False,
        is_canceled=False,
        is_shipped=False,
    )
    _update_order(
        other_user_order["id"],
        created_at=datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc),
        status=amocrm_client.STATUS_WORDS[amocrm_client.STATUS_IDS["won"]],
        is_active=False,
        is_paid=True,
        is_canceled=False,
        is_shipped=True,
    )

    response = client.get(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        params={"limit": 10},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    payload_by_id = {item["id"]: item for item in payload}

    assert set(payload_by_id) == {created_order["id"], sent_order["id"], delivered_order["id"], unknown_order["id"]}
    assert payload_by_id[created_order["id"]]["status_code"] == "created"
    assert payload_by_id[created_order["id"]]["history_bucket"] == "active"
    assert payload_by_id[sent_order["id"]]["status_code"] == "sent"
    assert payload_by_id[sent_order["id"]]["history_bucket"] == "active"
    assert payload_by_id[delivered_order["id"]]["status_code"] == "delivered"
    assert payload_by_id[delivered_order["id"]]["history_bucket"] == "completed"
    assert payload_by_id[unknown_order["id"]]["status_code"] == "created"
    assert payload_by_id[unknown_order["id"]]["history_bucket"] == "active"

    active_response = client.get(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        params={"history_bucket": "active", "limit": 10},
    )
    assert active_response.status_code == 200, active_response.text
    assert {item["id"] for item in active_response.json()} == {created_order["id"], sent_order["id"], unknown_order["id"]}

    completed_response = client.get(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        params={"history_bucket": "completed", "limit": 10},
    )
    assert completed_response.status_code == 200, completed_response.text
    assert [item["id"] for item in completed_response.json()] == [delivered_order["id"]]

    sent_response = client.get(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        params={"history_bucket": "active", "status_code": "sent", "limit": 10},
    )
    assert sent_response.status_code == 200, sent_response.text
    assert [item["id"] for item in sent_response.json()] == [sent_order["id"]]

    created_response = client.get(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        params={"history_bucket": "active", "status_code": "created", "limit": 10},
    )
    assert created_response.status_code == 200, created_response.text
    assert {item["id"] for item in created_response.json()} == {created_order["id"], unknown_order["id"]}

    dated_response = client.get(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        params={
            "created_from": datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc).isoformat(),
            "created_to": datetime(2026, 4, 12, 23, 59, tzinfo=timezone.utc).isoformat(),
            "limit": 10,
        },
    )
    assert dated_response.status_code == 200, dated_response.text
    assert {item["id"] for item in dated_response.json()} == {sent_order["id"], delivered_order["id"]}

    paginated_response = client.get(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        params={"limit": 1, "offset": 1},
    )
    assert paginated_response.status_code == 200, paginated_response.text
    assert [item["id"] for item in paginated_response.json()] == [delivered_order["id"]]


def test_upsert_my_push_token_reassigns_same_device_to_latest_user(client: TestClient, registered_user, second_registered_user):
    token_payload = {
        "expo_push_token": "ExponentPushToken[test-device-1]",
        "platform": "ios",
    }

    first_response = client.post(
        "/api/v1/users/me/push-tokens",
        headers=registered_user["headers"],
        json=token_payload,
    )
    assert first_response.status_code == 200, first_response.text
    assert first_response.json()["user_id"] == registered_user["user_id"]

    second_response = client.post(
        "/api/v1/users/me/push-tokens",
        headers=second_registered_user["headers"],
        json=token_payload,
    )
    assert second_response.status_code == 200, second_response.text
    assert second_response.json()["user_id"] == second_registered_user["user_id"]

    assert _get_push_tokens_for_user(registered_user["user_id"]) == []
    assert _get_push_tokens_for_user(second_registered_user["user_id"]) == [token_payload["expo_push_token"]]


def test_amocrm_webhook_sends_push_notification_on_order_status_change(
    client: TestClient,
    registered_user,
    variant_factory,
    stub_amocrm,
    monkeypatch,
):
    catalog = variant_factory(stock=5, price=Decimal("18.00"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])

    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "later"},
    )
    assert order_response.status_code == 200, order_response.text
    order_id = order_response.json()["id"]
    order_number = order_response.json()["order_number"]

    token_response = client.post(
        "/api/v1/users/me/push-tokens",
        headers=registered_user["headers"],
        json={"expo_push_token": "ExponentPushToken[notify-me]", "platform": "ios"},
    )
    assert token_response.status_code == 200, token_response.text

    sent_messages: list[dict] = []

    async def fake_send_expo_push_messages(messages):
        sent_messages.extend(messages)
        return set()

    async def fake_get_lead(lead_id):
        return {
            "id": lead_id,
            "name": f"Заказ №{order_number} с Приложения",
            "status_id": amocrm_client.STATUS_IDS["package_sent"],
            "pipeline_id": amocrm_client.PIPELINE_ID,
        }

    monkeypatch.setattr("src.app.services.push_notifications._send_expo_push_messages", fake_send_expo_push_messages)
    monkeypatch.setattr("src.app.modules.webhooks.router.amocrm_client.get_lead", fake_get_lead)

    webhook_body = (
        f"leads[status][0][id]=67890&"
        f"leads[status][0][status_id]={amocrm_client.STATUS_IDS['package_sent']}&"
        f"leads[status][0][pipeline_id]={amocrm_client.PIPELINE_ID}"
    )
    webhook_response = client.post(
        "/api/v1/webhooks/amocrm",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        content=webhook_body,
    )

    assert webhook_response.status_code == 200, webhook_response.text
    assert len(sent_messages) == 1
    assert sent_messages[0]["to"] == "ExponentPushToken[notify-me]"
    assert sent_messages[0]["title"] == f"Заказ №{order_number}"
    assert sent_messages[0]["data"]["order_id"] == order_id
    assert sent_messages[0]["data"]["status_code"] == "sent"
    assert sent_messages[0]["data"]["history_bucket"] == "active"


def test_amocrm_webhook_skips_push_notification_when_status_does_not_change(
    client: TestClient,
    registered_user,
    variant_factory,
    stub_amocrm,
    monkeypatch,
):
    catalog = variant_factory(stock=5, price=Decimal("18.00"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])

    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "later"},
    )
    assert order_response.status_code == 200, order_response.text
    order_id = order_response.json()["id"]
    order_number = order_response.json()["order_number"]

    token_response = client.post(
        "/api/v1/users/me/push-tokens",
        headers=registered_user["headers"],
        json={"expo_push_token": "ExponentPushToken[skip-me]", "platform": "ios"},
    )
    assert token_response.status_code == 200, token_response.text

    sent_messages: list[dict] = []

    async def fake_send_expo_push_messages(messages):
        sent_messages.extend(messages)
        return set()

    async def fake_get_lead(lead_id):
        return {
            "id": lead_id,
            "name": f"Заказ №{order_number} с Приложения",
            "status_id": amocrm_client.STATUS_IDS["main"],
            "pipeline_id": amocrm_client.PIPELINE_ID,
        }

    monkeypatch.setattr("src.app.services.push_notifications._send_expo_push_messages", fake_send_expo_push_messages)
    monkeypatch.setattr("src.app.modules.webhooks.router.amocrm_client.get_lead", fake_get_lead)

    webhook_body = (
        f"leads[status][0][id]=67890&"
        f"leads[status][0][status_id]={amocrm_client.STATUS_IDS['main']}&"
        f"leads[status][0][pipeline_id]={amocrm_client.PIPELINE_ID}"
    )
    webhook_response = client.post(
        "/api/v1/webhooks/amocrm",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        content=webhook_body,
    )

    assert webhook_response.status_code == 200, webhook_response.text
    assert sent_messages == []
