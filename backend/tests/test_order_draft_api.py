import sys
import types
import uuid
from datetime import datetime, timezone
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
from src.database.models import DeliveryAddress, DeliveryRecipient, OrderDraft, Product, User, Variant

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
            sku=f"draft-sku-{token[:20]}",
            name=f"Draft Product {token[:12]}",
            description=None,
            usage=None,
            expiration=None,
            priority=0,
        )
        session.add(product)
        session.flush()

        variant = Variant(
            product_id=product.id,
            sku=f"draft-var-{token[:20]}",
            name=f"Draft Variant {token[:8]}",
            stock=stock,
            price=price,
        )
        session.add(variant)
        session.commit()
        session.refresh(product)
        session.refresh(variant)
        return {"product_id": product.id, "variant_id": variant.id}


def _update_variant_stock(variant_id: int, stock: int) -> None:
    with Session(sync_engine) as session:
        variant = session.get(Variant, variant_id)
        assert variant is not None
        variant.stock = stock
        session.commit()


def _get_order_draft_count(user_id: int) -> int:
    with Session(sync_engine) as session:
        stmt = select(OrderDraft).where(OrderDraft.user_id == user_id)
        return len(list(session.execute(stmt).scalars().all()))


def _get_delivery_address_count(user_id: int) -> int:
    with Session(sync_engine) as session:
        stmt = select(DeliveryAddress).where(DeliveryAddress.user_id == user_id)
        return len(list(session.execute(stmt).scalars().all()))


def _get_delivery_recipient_count(user_id: int) -> int:
    with Session(sync_engine) as session:
        stmt = select(DeliveryRecipient).where(DeliveryRecipient.user_id == user_id)
        return len(list(session.execute(stmt).scalars().all()))


def _update_order_draft(draft_id: int, **fields) -> None:
    with Session(sync_engine) as session:
        draft = session.get(OrderDraft, draft_id)
        assert draft is not None
        for field, value in fields.items():
            setattr(draft, field, value)
        session.commit()


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


def _build_door_payload() -> dict:
    return {
        "mode": "door",
        "provider": "CDEK",
        "country_code": "RU",
        "name": "Москва, ул. Пушкина, 10",
        "full_address": "Россия, Москва, ул. Пушкина, 10",
        "details": "Подъезд 2",
        "city": "Москва",
        "postal_code": "101000",
        "latitude": 55.751244,
        "longitude": 37.618423,
        "provider_reference": None,
        "delivery_calculation": {
            "delivery_sum": "299.00",
            "period_min": 1,
            "period_max": 2,
            "currency": "RUB",
        },
    }


@pytest.fixture()
def registered_user(register_verified_user):
    token = uuid.uuid4().hex[:12]
    email = f"draft_{token}@example.com"
    payload = register_verified_user({
        "username": f"u{token}",
        "email": email,
        "password": "test-password",
        "name": "Draft",
        "surname": "Tester",
    })
    user_id = payload["user"]["id"]

    try:
        yield {"email": email, "user_id": user_id, "headers": {"Authorization": f"Bearer {payload['access_token']}"}}
    finally:
        _delete_user(user_id)


@pytest.fixture()
def second_registered_user(register_verified_user):
    token = uuid.uuid4().hex[:12]
    email = f"draft_second_{token}@example.com"
    payload = register_verified_user({
        "username": f"u{token}",
        "email": email,
        "password": "test-password",
        "name": "Second",
        "surname": "Tester",
    })
    user_id = payload["user"]["id"]

    try:
        yield {"email": email, "user_id": user_id, "headers": {"Authorization": f"Bearer {payload['access_token']}"}}
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


def test_create_pickup_order_draft_creates_address_and_clears_basket(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=5, price=Decimal("12.50"))

    add_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": catalog["variant_id"], "quantity": 2},
    )
    assert add_item_response.status_code == 200, add_item_response.text

    response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["delivery_address"]["mode"] == "pickup"
    assert payload["delivery_address"]["provider"] == "CDEK"
    assert payload["delivery_address"]["provider_reference"] == "MSK-PVZ-10"
    assert payload["items_count"] == 1
    assert payload["total_quantity"] == 2
    assert _decimal(payload["basket_subtotal"]) == Decimal("25.00")
    assert _decimal(payload["delivery_total"]) == Decimal("199.00")
    assert _decimal(payload["grand_total"]) == Decimal("224.00")
    assert payload["items"][0]["product_id"] == catalog["product_id"]
    assert payload["items"][0]["variant_id"] == catalog["variant_id"]
    assert payload["items"][0]["product_name"]
    assert _decimal(payload["items"][0]["unit_price"]) == Decimal("12.50")
    assert _decimal(payload["items"][0]["line_total"]) == Decimal("25.00")
    assert payload["items"][0]["image_url"].endswith("/media/products/product.png")
    assert payload["recipient"] is None
    assert _get_order_draft_count(registered_user["user_id"]) == 1
    assert _get_delivery_address_count(registered_user["user_id"]) == 1
    assert _get_delivery_recipient_count(registered_user["user_id"]) == 0

    basket_response = client.get("/api/v1/users/me/basket", headers=registered_user["headers"])
    assert basket_response.status_code == 200, basket_response.text
    basket_payload = basket_response.json()
    assert basket_payload["items"] == []
    assert basket_payload["items_count"] == 0
    assert basket_payload["total_quantity"] == 0


def test_create_door_order_draft_creates_snapshot(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=3, price=Decimal("9.50"))

    add_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": catalog["variant_id"], "quantity": 1},
    )
    assert add_item_response.status_code == 200, add_item_response.text

    response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_door_payload(),
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["delivery_address"]["mode"] == "door"
    assert payload["delivery_address"]["details"] == "Подъезд 2"
    assert payload["delivery_period_min"] == 1
    assert payload["delivery_period_max"] == 2
    assert _decimal(payload["basket_subtotal"]) == Decimal("9.50")
    assert _decimal(payload["delivery_total"]) == Decimal("299.00")
    assert _decimal(payload["grand_total"]) == Decimal("308.50")


def test_create_order_draft_without_delivery_creates_draft(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=4, price=Decimal("11.00"))

    add_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": catalog["variant_id"], "quantity": 2},
    )
    assert add_item_response.status_code == 200, add_item_response.text

    response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json={"draft_name": "Корзина без доставки"},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["delivery_address_id"] is None
    assert payload["delivery_address"] is None
    assert payload["draft_name"] == "Корзина без доставки"
    assert _decimal(payload["basket_subtotal"]) == Decimal("22.00")
    assert _decimal(payload["delivery_total"]) == Decimal("0.00")
    assert _decimal(payload["grand_total"]) == Decimal("22.00")
    assert payload["currency"] == "RUB"
    assert payload["delivery_period_min"] is None
    assert payload["delivery_period_max"] is None
    assert _get_order_draft_count(registered_user["user_id"]) == 1
    assert _get_delivery_address_count(registered_user["user_id"]) == 0

    basket_response = client.get("/api/v1/users/me/basket", headers=registered_user["headers"])
    assert basket_response.status_code == 200, basket_response.text
    basket_payload = basket_response.json()
    assert basket_payload["items"] == []
    assert basket_payload["items_count"] == 0
    assert basket_payload["total_quantity"] == 0


def test_create_order_draft_rejects_empty_basket(client: TestClient, registered_user):
    response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )

    assert response.status_code == 409, response.text
    assert _get_order_draft_count(registered_user["user_id"]) == 0
    assert _get_delivery_address_count(registered_user["user_id"]) == 0


def test_create_order_draft_rejects_unavailable_items_without_clearing_basket(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=2, price=Decimal("15.00"))

    add_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": catalog["variant_id"], "quantity": 2},
    )
    assert add_item_response.status_code == 200, add_item_response.text

    _update_variant_stock(catalog["variant_id"], 1)

    response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )

    assert response.status_code == 409, response.text
    assert _get_order_draft_count(registered_user["user_id"]) == 0
    assert _get_delivery_address_count(registered_user["user_id"]) == 0

    basket_response = client.get("/api/v1/users/me/basket", headers=registered_user["headers"])
    assert basket_response.status_code == 200, basket_response.text
    basket_payload = basket_response.json()
    assert basket_payload["items_count"] == 1
    assert basket_payload["total_quantity"] == 2


def test_create_order_draft_rejects_duplicate_products_without_clearing_basket(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=5, price=Decimal("12.50"))

    first_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": catalog["variant_id"], "quantity": 2},
    )
    assert first_add_response.status_code == 200, first_add_response.text

    first_create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert first_create_response.status_code == 201, first_create_response.text
    first_draft_id = first_create_response.json()["id"]

    second_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": catalog["variant_id"], "quantity": 2},
    )
    assert second_add_response.status_code == 200, second_add_response.text

    duplicate_create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )

    assert duplicate_create_response.status_code == 409, duplicate_create_response.text
    duplicate_payload = duplicate_create_response.json()
    assert duplicate_payload["detail"]["message"] == "Черновик с такими товарами уже существует"
    assert duplicate_payload["detail"]["draft_id"] == first_draft_id
    assert _get_order_draft_count(registered_user["user_id"]) == 1

    basket_response = client.get("/api/v1/users/me/basket", headers=registered_user["headers"])
    assert basket_response.status_code == 200, basket_response.text
    basket_payload = basket_response.json()
    assert basket_payload["items_count"] == 1
    assert basket_payload["total_quantity"] == 2


def test_create_order_draft_reuses_existing_delivery_address(client: TestClient, registered_user, variant_factory):
    first_catalog = variant_factory(stock=5, price=Decimal("12.50"))
    second_catalog = variant_factory(stock=5, price=Decimal("8.00"))

    first_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": first_catalog["variant_id"], "quantity": 1},
    )
    assert first_add_response.status_code == 200, first_add_response.text

    first_create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert first_create_response.status_code == 201, first_create_response.text
    first_payload = first_create_response.json()

    second_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": second_catalog["variant_id"], "quantity": 1},
    )
    assert second_add_response.status_code == 200, second_add_response.text

    second_create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json={
            **_build_pickup_payload(),
            "name": "Тот же адрес, другое имя",
        },
    )
    assert second_create_response.status_code == 201, second_create_response.text
    second_payload = second_create_response.json()

    assert second_payload["delivery_address"]["id"] == first_payload["delivery_address"]["id"]
    assert _get_delivery_address_count(registered_user["user_id"]) == 1


def test_get_latest_order_draft_returns_newest_for_user(client: TestClient, registered_user, variant_factory):
    first_variant = variant_factory(stock=5, price=Decimal("5.00"))
    second_variant = variant_factory(stock=5, price=Decimal("7.00"))

    first_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": first_variant["variant_id"], "quantity": 1},
    )
    assert first_add_response.status_code == 200, first_add_response.text

    first_draft_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert first_draft_response.status_code == 201, first_draft_response.text
    first_draft_id = first_draft_response.json()["id"]

    second_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": second_variant["variant_id"], "quantity": 1},
    )
    assert second_add_response.status_code == 200, second_add_response.text

    second_draft_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_door_payload(),
    )
    assert second_draft_response.status_code == 201, second_draft_response.text
    second_draft_id = second_draft_response.json()["id"]

    latest_response = client.get("/api/v1/users/me/order-drafts/latest", headers=registered_user["headers"])
    assert latest_response.status_code == 200, latest_response.text
    latest_payload = latest_response.json()
    assert latest_payload["id"] == second_draft_id
    assert latest_payload["id"] != first_draft_id


def test_get_order_drafts_returns_recent_drafts_for_user(client: TestClient, registered_user, variant_factory):
    first_variant = variant_factory(stock=5, price=Decimal("5.00"))
    second_variant = variant_factory(stock=5, price=Decimal("7.00"))

    first_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": first_variant["variant_id"], "quantity": 1},
    )
    assert first_add_response.status_code == 200, first_add_response.text

    first_draft_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert first_draft_response.status_code == 201, first_draft_response.text
    first_draft_id = first_draft_response.json()["id"]

    second_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": second_variant["variant_id"], "quantity": 1},
    )
    assert second_add_response.status_code == 200, second_add_response.text

    second_draft_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_door_payload(),
    )
    assert second_draft_response.status_code == 201, second_draft_response.text
    second_draft_id = second_draft_response.json()["id"]

    drafts_response = client.get(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        params={"limit": 2},
    )

    assert drafts_response.status_code == 200, drafts_response.text
    drafts_payload = drafts_response.json()
    assert len(drafts_payload) == 2
    assert drafts_payload[0]["id"] == second_draft_id
    assert drafts_payload[1]["id"] == first_draft_id
    assert drafts_payload[0]["items"][0]["image_url"].endswith("/media/products/product.png")


def test_update_order_draft_metadata(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=5, price=Decimal("12.50"))

    add_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": catalog["variant_id"], "quantity": 1},
    )
    assert add_item_response.status_code == 200, add_item_response.text

    create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert create_response.status_code == 201, create_response.text
    draft_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/users/me/order-drafts/{draft_id}",
        headers=registered_user["headers"],
        json={
            "draft_name": "Майский курс",
            "comment": "Оставить у консьержа",
        },
    )

    assert update_response.status_code == 200, update_response.text
    update_payload = update_response.json()
    assert update_payload["draft_name"] == "Майский курс"
    assert update_payload["comment"] == "Оставить у консьержа"

    clear_response = client.patch(
        f"/api/v1/users/me/order-drafts/{draft_id}",
        headers=registered_user["headers"],
        json={
            "draft_name": "   ",
            "comment": None,
        },
    )

    assert clear_response.status_code == 200, clear_response.text
    clear_payload = clear_response.json()
    assert clear_payload["draft_name"] is None
    assert clear_payload["comment"] is None


def test_update_order_draft_can_sync_items_from_basket(client: TestClient, registered_user, variant_factory):
    draft_catalog = variant_factory(stock=5, price=Decimal("12.50"))
    added_catalog = variant_factory(stock=5, price=Decimal("8.00"))

    add_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": draft_catalog["variant_id"], "quantity": 1},
    )
    assert add_item_response.status_code == 200, add_item_response.text

    create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert create_response.status_code == 201, create_response.text
    draft_id = create_response.json()["id"]

    restore_response = client.post(
        f"/api/v1/users/me/basket/restore-draft/{draft_id}",
        headers=registered_user["headers"],
    )
    assert restore_response.status_code == 200, restore_response.text

    add_new_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": added_catalog["variant_id"], "quantity": 2},
    )
    assert add_new_item_response.status_code == 200, add_new_item_response.text

    sync_response = client.patch(
        f"/api/v1/users/me/order-drafts/{draft_id}",
        headers=registered_user["headers"],
        json={"sync_basket_items": True},
    )

    assert sync_response.status_code == 200, sync_response.text
    sync_payload = sync_response.json()
    assert sync_payload["items_count"] == 2
    assert sync_payload["total_quantity"] == 3
    assert _decimal(sync_payload["basket_subtotal"]) == Decimal("28.50")
    assert _decimal(sync_payload["grand_total"]) == Decimal("227.50")

    quantities_by_variant_id = {
        item["variant_id"]: item["quantity"]
        for item in sync_payload["items"]
    }
    assert quantities_by_variant_id == {
        draft_catalog["variant_id"]: 1,
        added_catalog["variant_id"]: 2,
    }

    basket_response = client.get("/api/v1/users/me/basket", headers=registered_user["headers"])
    assert basket_response.status_code == 200, basket_response.text
    basket_payload = basket_response.json()
    assert basket_payload["items"] == []
    assert basket_payload["items_count"] == 0
    assert basket_payload["total_quantity"] == 0


def test_update_order_draft_can_clear_items_when_syncing_empty_basket(client: TestClient, registered_user, variant_factory):
    draft_catalog = variant_factory(stock=5, price=Decimal("12.50"))

    add_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": draft_catalog["variant_id"], "quantity": 1},
    )
    assert add_item_response.status_code == 200, add_item_response.text

    create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert create_response.status_code == 201, create_response.text
    draft_id = create_response.json()["id"]

    restore_response = client.post(
        f"/api/v1/users/me/basket/restore-draft/{draft_id}",
        headers=registered_user["headers"],
    )
    assert restore_response.status_code == 200, restore_response.text

    clear_response = client.delete(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
    )
    assert clear_response.status_code == 200, clear_response.text

    sync_response = client.patch(
        f"/api/v1/users/me/order-drafts/{draft_id}",
        headers=registered_user["headers"],
        json={"sync_basket_items": True},
    )

    assert sync_response.status_code == 200, sync_response.text
    sync_payload = sync_response.json()
    assert sync_payload["items"] == []
    assert sync_payload["items_count"] == 0
    assert sync_payload["total_quantity"] == 0
    assert _decimal(sync_payload["basket_subtotal"]) == Decimal("0.00")
    assert _decimal(sync_payload["delivery_total"]) == Decimal("199.00")
    assert _decimal(sync_payload["grand_total"]) == Decimal("199.00")

    basket_response = client.get("/api/v1/users/me/basket", headers=registered_user["headers"])
    assert basket_response.status_code == 200, basket_response.text
    basket_payload = basket_response.json()
    assert basket_payload["items"] == []
    assert basket_payload["items_count"] == 0
    assert basket_payload["total_quantity"] == 0


def test_delete_order_draft_removes_draft(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=5, price=Decimal("12.50"))

    add_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": catalog["variant_id"], "quantity": 1},
    )
    assert add_item_response.status_code == 200, add_item_response.text

    create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert create_response.status_code == 201, create_response.text
    draft_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/users/me/order-drafts/{draft_id}",
        headers=registered_user["headers"],
    )

    assert delete_response.status_code == 204, delete_response.text
    assert _get_order_draft_count(registered_user["user_id"]) == 0

    fetch_response = client.get(
        f"/api/v1/users/me/order-drafts/{draft_id}",
        headers=registered_user["headers"],
    )
    assert fetch_response.status_code == 404, fetch_response.text


def test_get_order_draft_options_returns_previous_addresses_and_recipients(client: TestClient, registered_user, variant_factory):
    first_variant = variant_factory(stock=5, price=Decimal("12.50"))
    second_variant = variant_factory(stock=5, price=Decimal("9.00"))

    first_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": first_variant["variant_id"], "quantity": 1},
    )
    assert first_add_response.status_code == 200, first_add_response.text

    first_create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert first_create_response.status_code == 201, first_create_response.text

    second_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": second_variant["variant_id"], "quantity": 1},
    )
    assert second_add_response.status_code == 200, second_add_response.text

    second_create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_door_payload(),
    )
    assert second_create_response.status_code == 201, second_create_response.text
    second_draft_id = second_create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/users/me/order-drafts/{second_draft_id}",
        headers=registered_user["headers"],
        json={
            "new_recipient": {
                "name": "Другой",
                "surname": "получатель",
                "phone": "+7 999 000-00-00",
                "email": "recipient@example.com",
            },
        },
    )
    assert update_response.status_code == 200, update_response.text

    options_response = client.get(
        f"/api/v1/users/me/order-drafts/{second_draft_id}/options",
        headers=registered_user["headers"],
    )

    assert options_response.status_code == 200, options_response.text
    options_payload = options_response.json()
    assert len(options_payload["addresses"]) == 2
    assert len(options_payload["recipients"]) == 1
    assert any(recipient["name"] == "Другой" and recipient["surname"] == "Получатель" for recipient in options_payload["recipients"])


def test_update_order_draft_can_switch_address_and_save_new_checkout_details(client: TestClient, registered_user, variant_factory):
    first_variant = variant_factory(stock=5, price=Decimal("12.50"))
    second_variant = variant_factory(stock=5, price=Decimal("8.00"))

    first_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": first_variant["variant_id"], "quantity": 1},
    )
    assert first_add_response.status_code == 200, first_add_response.text

    first_create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert first_create_response.status_code == 201, first_create_response.text
    first_draft_payload = first_create_response.json()
    first_draft_id = first_draft_payload["id"]

    second_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": second_variant["variant_id"], "quantity": 1},
    )
    assert second_add_response.status_code == 200, second_add_response.text

    second_create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_door_payload(),
    )
    assert second_create_response.status_code == 201, second_create_response.text
    second_draft_payload = second_create_response.json()

    recipient_create_response = client.patch(
        f"/api/v1/users/me/order-drafts/{second_draft_payload['id']}",
        headers=registered_user["headers"],
        json={
            "new_recipient": {
                "name": "Другой",
                "surname": "получатель",
                "phone": "+7 999 000-00-00",
                "email": "recipient@example.com",
            },
        },
    )

    assert recipient_create_response.status_code == 200, recipient_create_response.text
    second_draft_payload = recipient_create_response.json()

    switch_response = client.patch(
        f"/api/v1/users/me/order-drafts/{first_draft_id}",
        headers=registered_user["headers"],
        json={
            "delivery_address_id": second_draft_payload["delivery_address"]["id"],
            "recipient_id": second_draft_payload["recipient"]["id"],
        },
    )

    assert switch_response.status_code == 200, switch_response.text
    switch_payload = switch_response.json()
    assert switch_payload["delivery_address"]["id"] == second_draft_payload["delivery_address"]["id"]
    assert switch_payload["recipient"]["id"] == second_draft_payload["recipient"]["id"]
    assert switch_payload["recipient"]["email"] == second_draft_payload["recipient"]["email"]

    delivery_address_count_before = _get_delivery_address_count(registered_user["user_id"])

    create_address_response = client.patch(
        f"/api/v1/users/me/order-drafts/{first_draft_id}",
        headers=registered_user["headers"],
        json={
            "new_delivery_address": {
                "full_address": "Россия, Москва, ул. Новая, 12",
                "details": "Квартира 8",
            }
        },
    )

    assert create_address_response.status_code == 200, create_address_response.text
    create_address_payload = create_address_response.json()
    assert create_address_payload["delivery_address"]["full_address"] == "Россия, Москва, ул. Новая, 12"
    assert create_address_payload["delivery_address"]["details"] == "Квартира 8"
    assert _get_delivery_address_count(registered_user["user_id"]) == delivery_address_count_before + 1


def test_update_order_draft_reuses_existing_delivery_address(client: TestClient, registered_user, variant_factory):
    first_variant = variant_factory(stock=5, price=Decimal("12.50"))
    second_variant = variant_factory(stock=5, price=Decimal("8.00"))

    first_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": first_variant["variant_id"], "quantity": 1},
    )
    assert first_add_response.status_code == 200, first_add_response.text

    first_create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert first_create_response.status_code == 201, first_create_response.text
    first_payload = first_create_response.json()

    second_add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": second_variant["variant_id"], "quantity": 1},
    )
    assert second_add_response.status_code == 200, second_add_response.text

    second_create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_door_payload(),
    )
    assert second_create_response.status_code == 201, second_create_response.text
    second_payload = second_create_response.json()

    update_response = client.patch(
        f"/api/v1/users/me/order-drafts/{second_payload['id']}",
        headers=registered_user["headers"],
        json={
            "new_delivery_address": {
                "mode": "pickup",
                "provider": "CDEK",
                "country_code": "RU",
                "name": "Тот же адрес, другое имя",
                "full_address": "Россия, Москва, ул. Пушкина, 10",
                "details": "Пн-Вс 10:00-20:00",
                "city": "Москва",
                "postal_code": "101000",
                "latitude": 55.751244,
                "longitude": 37.618423,
                "provider_reference": "MSK-PVZ-10",
            },
        },
    )

    assert update_response.status_code == 200, update_response.text
    update_payload = update_response.json()
    assert update_payload["delivery_address"]["id"] == first_payload["delivery_address"]["id"]
    assert _get_delivery_address_count(registered_user["user_id"]) == 2


def test_restore_order_draft_replaces_existing_basket_contents(client: TestClient, registered_user, variant_factory):
    draft_catalog = variant_factory(stock=5, price=Decimal("12.50"))
    replacement_catalog = variant_factory(stock=5, price=Decimal("7.00"))

    add_draft_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": draft_catalog["variant_id"], "quantity": 2},
    )
    assert add_draft_item_response.status_code == 200, add_draft_item_response.text

    create_draft_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert create_draft_response.status_code == 201, create_draft_response.text
    draft_id = create_draft_response.json()["id"]

    add_replacement_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": replacement_catalog["variant_id"], "quantity": 1},
    )
    assert add_replacement_item_response.status_code == 200, add_replacement_item_response.text

    restore_response = client.post(
        f"/api/v1/users/me/basket/restore-draft/{draft_id}",
        headers=registered_user["headers"],
    )

    assert restore_response.status_code == 200, restore_response.text
    basket_payload = restore_response.json()
    assert basket_payload["items_count"] == 1
    assert basket_payload["total_quantity"] == 2
    assert basket_payload["items"][0]["variant_id"] == draft_catalog["variant_id"]
    assert _decimal(basket_payload["items"][0]["unit_price"]) == Decimal("12.50")
    assert _decimal(basket_payload["items"][0]["line_total"]) == Decimal("25.00")


def test_restore_order_draft_rejects_unavailable_items_without_clearing_current_basket(client: TestClient, registered_user, variant_factory):
    draft_catalog = variant_factory(stock=5, price=Decimal("12.50"))
    current_catalog = variant_factory(stock=5, price=Decimal("9.00"))

    add_draft_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": draft_catalog["variant_id"], "quantity": 2},
    )
    assert add_draft_item_response.status_code == 200, add_draft_item_response.text

    create_draft_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert create_draft_response.status_code == 201, create_draft_response.text
    draft_id = create_draft_response.json()["id"]

    add_current_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": current_catalog["variant_id"], "quantity": 1},
    )
    assert add_current_item_response.status_code == 200, add_current_item_response.text

    _update_variant_stock(draft_catalog["variant_id"], 1)

    restore_response = client.post(
        f"/api/v1/users/me/basket/restore-draft/{draft_id}",
        headers=registered_user["headers"],
    )

    assert restore_response.status_code == 409, restore_response.text

    basket_response = client.get("/api/v1/users/me/basket", headers=registered_user["headers"])
    assert basket_response.status_code == 200, basket_response.text
    basket_payload = basket_response.json()
    assert basket_payload["items_count"] == 1
    assert basket_payload["total_quantity"] == 1
    assert basket_payload["items"][0]["variant_id"] == current_catalog["variant_id"]


def test_get_order_draft_rejects_cross_user_access(client: TestClient, registered_user, second_registered_user, variant_factory):
    catalog = variant_factory(stock=5, price=Decimal("12.00"))

    add_item_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": catalog["variant_id"], "quantity": 1},
    )
    assert add_item_response.status_code == 200, add_item_response.text

    create_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert create_response.status_code == 201, create_response.text
    draft_id = create_response.json()["id"]

    forbidden_response = client.get(
        f"/api/v1/users/me/order-drafts/{draft_id}",
        headers=second_registered_user["headers"],
    )

    assert forbidden_response.status_code == 404, forbidden_response.text

    forbidden_patch_response = client.patch(
        f"/api/v1/users/me/order-drafts/{draft_id}",
        headers=second_registered_user["headers"],
        json={"draft_name": "Чужой черновик"},
    )

    assert forbidden_patch_response.status_code == 404, forbidden_patch_response.text


def test_list_order_drafts_supports_offset_and_created_filters(
    client: TestClient,
    registered_user,
    second_registered_user,
    variant_factory,
):
    def create_draft(headers: dict[str, str], variant_id: int, quantity: int) -> dict:
        add_item_response = client.post(
            "/api/v1/users/me/basket/items",
            headers=headers,
            json={"variant_id": variant_id, "quantity": quantity},
        )
        assert add_item_response.status_code == 200, add_item_response.text

        create_response = client.post(
            "/api/v1/users/me/order-drafts",
            headers=headers,
            json=_build_pickup_payload(),
        )
        assert create_response.status_code == 201, create_response.text
        return create_response.json()

    first_draft = create_draft(registered_user["headers"], variant_factory(stock=5, price=Decimal("12.00"))["variant_id"], 1)
    second_draft = create_draft(registered_user["headers"], variant_factory(stock=5, price=Decimal("14.00"))["variant_id"], 1)
    third_draft = create_draft(registered_user["headers"], variant_factory(stock=5, price=Decimal("16.00"))["variant_id"], 1)
    other_user_draft = create_draft(second_registered_user["headers"], variant_factory(stock=5, price=Decimal("18.00"))["variant_id"], 1)

    _update_order_draft(first_draft["id"], created_at=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc))
    _update_order_draft(second_draft["id"], created_at=datetime(2026, 4, 11, 9, 0, tzinfo=timezone.utc))
    _update_order_draft(third_draft["id"], created_at=datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc))
    _update_order_draft(other_user_draft["id"], created_at=datetime(2026, 4, 13, 9, 0, tzinfo=timezone.utc))

    response = client.get(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        params={"limit": 10},
    )
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [third_draft["id"], second_draft["id"], first_draft["id"]]

    paginated_response = client.get(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        params={"limit": 1, "offset": 1},
    )
    assert paginated_response.status_code == 200, paginated_response.text
    assert [item["id"] for item in paginated_response.json()] == [second_draft["id"]]

    dated_response = client.get(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        params={
            "created_from": datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc).isoformat(),
            "created_to": datetime(2026, 4, 11, 23, 59, tzinfo=timezone.utc).isoformat(),
            "limit": 10,
        },
    )
    assert dated_response.status_code == 200, dated_response.text
    assert [item["id"] for item in dated_response.json()] == [second_draft["id"]]
