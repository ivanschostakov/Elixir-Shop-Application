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
from src.database.models import Product, User, Variant

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
            sku=f"basket-sku-{token[:20]}", name=f"Basket Product {token[:12]}", description=None, usage=None, expiration=None, priority=0
        )
        session.add(product)
        session.flush()

        variant = Variant(
            product_id=product.id, sku=f"basket-var-{token[:20]}", name=f"Basket Variant {token[:8]}", stock=stock, price=price
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


@pytest.fixture()
def registered_user(client: TestClient):
    token = uuid.uuid4().hex[:12]
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u{token}",
            "email": f"basket_{token}@example.com",
            "password": "test-password",
            "name": "Basket",
            "surname": "Tester",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    user_id = payload["user"]["id"]

    try:
        yield {"user_id": user_id, "headers": {"Authorization": f"Bearer {payload['access_token']}"}}
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


def test_get_empty_basket_returns_hydrated_response(client: TestClient, registered_user):
    response = client.get("/api/v1/users/me/basket", headers=registered_user["headers"])

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user_id"] == registered_user["user_id"]
    assert payload["items"] == []
    assert payload["items_count"] == 0
    assert payload["total_quantity"] == 0
    assert _decimal(payload["total_amount"]) == Decimal("0.00")
    assert payload["has_unavailable_items"] is False


def test_post_basket_alias_returns_hydrated_response(client: TestClient, registered_user):
    response = client.post("/api/v1/users/me/basket", headers=registered_user["headers"])

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user_id"] == registered_user["user_id"]
    assert payload["items"] == []


def test_add_item_returns_hydrated_basket(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=5, price=Decimal("12.50"))

    response = client.post(
        "/api/v1/users/me/basket/items", headers=registered_user["headers"], json={"variant_id": catalog["variant_id"], "quantity": 2}
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items_count"] == 1
    assert payload["total_quantity"] == 2
    assert _decimal(payload["total_amount"]) == Decimal("25.00")
    assert payload["has_unavailable_items"] is False

    item = payload["items"][0]
    assert item["variant_id"] == catalog["variant_id"]
    assert item["quantity"] == 2
    assert _decimal(item["unit_price"]) == Decimal("12.50")
    assert _decimal(item["line_total"]) == Decimal("25.00")
    assert item["available_quantity"] == 5
    assert item["is_available"] is True
    assert item["product"]["id"] == catalog["product_id"]
    assert item["variant"]["id"] == catalog["variant_id"]
    assert item["product"]["image_url"].endswith("/media/products/product.png")
    assert item["variant"]["image_url"].endswith("/media/products/product.png")


def test_adding_same_variant_twice_increments_single_line(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=5, price=Decimal("9.00"))

    first_response = client.post(
        "/api/v1/users/me/basket/items", headers=registered_user["headers"], json={"variant_id": catalog["variant_id"], "quantity": 1}
    )
    assert first_response.status_code == 200, first_response.text

    second_response = client.post(
        "/api/v1/users/me/basket/items", headers=registered_user["headers"], json={"variant_id": catalog["variant_id"], "quantity": 2}
    )

    assert second_response.status_code == 200, second_response.text
    payload = second_response.json()
    assert payload["items_count"] == 1
    assert payload["total_quantity"] == 3
    assert _decimal(payload["total_amount"]) == Decimal("27.00")
    assert payload["items"][0]["quantity"] == 3


def test_update_item_changes_quantity(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=5, price=Decimal("7.50"))
    create_response = client.post(
        "/api/v1/users/me/basket/items", headers=registered_user["headers"], json={"variant_id": catalog["variant_id"], "quantity": 1}
    )
    assert create_response.status_code == 200, create_response.text
    item_id = create_response.json()["items"][0]["id"]

    response = client.patch(f"/api/v1/users/me/basket/items/{item_id}", headers=registered_user["headers"], json={"quantity": 4})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items"][0]["quantity"] == 4
    assert payload["total_quantity"] == 4
    assert _decimal(payload["total_amount"]) == Decimal("30.00")


def test_delete_item_removes_line(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=5, price=Decimal("5.00"))
    create_response = client.post(
        "/api/v1/users/me/basket/items", headers=registered_user["headers"], json={"variant_id": catalog["variant_id"], "quantity": 2}
    )
    assert create_response.status_code == 200, create_response.text
    item_id = create_response.json()["items"][0]["id"]

    response = client.delete(f"/api/v1/users/me/basket/items/{item_id}", headers=registered_user["headers"])

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items"] == []
    assert payload["items_count"] == 0
    assert payload["total_quantity"] == 0


def test_clear_basket_empties_all_items(client: TestClient, registered_user, variant_factory):
    first_variant = variant_factory(stock=5, price=Decimal("3.00"))
    second_variant = variant_factory(stock=5, price=Decimal("4.50"))

    for variant_id, quantity in ((first_variant["variant_id"], 1), (second_variant["variant_id"], 2)):
        response = client.post(
            "/api/v1/users/me/basket/items", headers=registered_user["headers"], json={"variant_id": variant_id, "quantity": quantity}
        )
        assert response.status_code == 200, response.text

    response = client.delete("/api/v1/users/me/basket/items", headers=registered_user["headers"])

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items"] == []
    assert payload["items_count"] == 0
    assert payload["total_quantity"] == 0
    assert _decimal(payload["total_amount"]) == Decimal("0.00")


def test_unknown_variant_returns_404(client: TestClient, registered_user):
    response = client.post(
        "/api/v1/users/me/basket/items", headers=registered_user["headers"], json={"variant_id": 999999999, "quantity": 1}
    )

    assert response.status_code == 404, response.text


def test_unknown_basket_item_returns_404(client: TestClient, registered_user):
    response = client.delete("/api/v1/users/me/basket/items/999999999", headers=registered_user["headers"])

    assert response.status_code == 404, response.text


def test_zero_quantity_is_rejected(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=5, price=Decimal("8.00"))
    create_response = client.post(
        "/api/v1/users/me/basket/items", headers=registered_user["headers"], json={"variant_id": catalog["variant_id"], "quantity": 1}
    )
    assert create_response.status_code == 200, create_response.text
    item_id = create_response.json()["items"][0]["id"]

    add_response = client.post(
        "/api/v1/users/me/basket/items", headers=registered_user["headers"], json={"variant_id": catalog["variant_id"], "quantity": 0}
    )
    update_response = client.patch(f"/api/v1/users/me/basket/items/{item_id}", headers=registered_user["headers"], json={"quantity": 0})

    assert add_response.status_code == 422, add_response.text
    assert update_response.status_code == 422, update_response.text


def test_quantity_above_stock_returns_409(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=2, price=Decimal("11.00"))

    response = client.post(
        "/api/v1/users/me/basket/items", headers=registered_user["headers"], json={"variant_id": catalog["variant_id"], "quantity": 3}
    )

    assert response.status_code == 409, response.text


def test_stock_drift_marks_item_unavailable(client: TestClient, registered_user, variant_factory):
    catalog = variant_factory(stock=3, price=Decimal("10.00"))
    create_response = client.post(
        "/api/v1/users/me/basket/items", headers=registered_user["headers"], json={"variant_id": catalog["variant_id"], "quantity": 2}
    )
    assert create_response.status_code == 200, create_response.text

    _update_variant_stock(catalog["variant_id"], 1)

    response = client.get("/api/v1/users/me/basket", headers=registered_user["headers"])

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["has_unavailable_items"] is True
    assert payload["items"][0]["is_available"] is False
    assert payload["items"][0]["available_quantity"] == 1


def test_requires_authentication(client: TestClient):
    response = client.get("/api/v1/users/me/basket")

    assert response.status_code == 401, response.text
