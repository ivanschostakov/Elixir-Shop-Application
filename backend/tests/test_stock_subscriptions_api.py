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
from src.database.models import Product, StockNotificationSubscription, User, Variant

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
            sku=f"stock-sub-sku-{token[:20]}",
            name=f"Stock Sub Product {token[:12]}",
            description=None,
            usage=None,
            expiration=None,
            priority=0,
        )
        session.add(product)
        session.flush()

        variant = Variant(
            product_id=product.id,
            sku=f"stock-sub-var-{token[:20]}",
            name=f"Stock Sub Variant {token[:8]}",
            stock=stock,
            price=price,
        )
        session.add(variant)
        session.commit()
        return {"product_id": product.id, "variant_id": variant.id}


def _create_product_with_variant_stocks(stocks: list[int], *, price: Decimal) -> dict[str, object]:
    token = uuid.uuid4().hex
    with Session(sync_engine) as session:
        product = Product(
            sku=f"stock-sub-product-{token[:20]}",
            name=f"Stock Sub Product {token[:12]}",
            description=None,
            usage=None,
            expiration=None,
            priority=0,
        )
        session.add(product)
        session.flush()

        variant_ids: list[int] = []
        for index, stock in enumerate(stocks):
            variant = Variant(
                product_id=product.id,
                sku=f"stock-sub-var-{token[:16]}-{index}",
                name=f"Stock Sub Variant {token[:8]} {index}",
                stock=stock,
                price=price,
            )
            session.add(variant)
            session.flush()
            variant_ids.append(variant.id)

        session.commit()
        return {"product_id": product.id, "variant_ids": variant_ids}


def _get_stock_subscription(user_id: int, variant_id: int) -> StockNotificationSubscription | None:
    with Session(sync_engine) as session:
        stmt = select(StockNotificationSubscription).where(
            StockNotificationSubscription.user_id == user_id,
            StockNotificationSubscription.variant_id == variant_id,
        )
        return session.execute(stmt).scalar_one_or_none()


@pytest.fixture()
def registered_user(register_verified_user):
    token = uuid.uuid4().hex[:12]
    payload = register_verified_user(
        {
            "username": f"u{token}",
            "email": f"stock_sub_{token}@example.com",
            "password": "test-password",
            "name": "Stock",
            "surname": "Tester",
        }
    )
    user_id = payload["user"]["id"]

    try:
        yield {
            "user_id": user_id,
            "headers": {"Authorization": f"Bearer {payload['access_token']}"},
        }
    finally:
        _delete_user(user_id)


def test_upsert_stock_subscription_is_idempotent(client: TestClient, registered_user):
    catalog = _create_product_variant(stock=0, price=_decimal("10.00"))

    try:
        first = client.post(
            "/api/v1/users/me/stock-subscriptions",
            headers=registered_user["headers"],
            json={"variant_id": catalog["variant_id"]},
        )
        assert first.status_code == 200, first.text

        second = client.post(
            "/api/v1/users/me/stock-subscriptions",
            headers=registered_user["headers"],
            json={"variant_id": catalog["variant_id"]},
        )
        assert second.status_code == 200, second.text

        first_payload = first.json()
        second_payload = second.json()
        assert second_payload["id"] == first_payload["id"]
        assert second_payload["is_active"] is True
        assert second_payload["last_seen_stock"] == 0
        assert second_payload["notified_at"] is None
        assert second_payload["variant_id"] == catalog["variant_id"]
    finally:
        _delete_product(catalog["product_id"])


def test_favouriting_product_activates_low_stock_variant_subscriptions(client: TestClient, registered_user):
    catalog = _create_product_with_variant_stocks([0, 4, 11], price=_decimal("12.00"))
    product_id = int(catalog["product_id"])
    variant_ids = list(catalog["variant_ids"])

    try:
        favourite_response = client.post(
            f"/api/v1/users/me/favorites/products/{product_id}",
            headers=registered_user["headers"],
        )
        assert favourite_response.status_code == 201, favourite_response.text

        out_of_stock_subscription = _get_stock_subscription(registered_user["user_id"], variant_ids[0])
        low_stock_subscription = _get_stock_subscription(registered_user["user_id"], variant_ids[1])
        in_stock_subscription = _get_stock_subscription(registered_user["user_id"], variant_ids[2])

        assert out_of_stock_subscription is not None
        assert out_of_stock_subscription.is_active is True
        assert out_of_stock_subscription.last_seen_stock == 0
        assert low_stock_subscription is not None
        assert low_stock_subscription.is_active is True
        assert low_stock_subscription.last_seen_stock == 4
        assert in_stock_subscription is None

        delete_response = client.delete(
            f"/api/v1/users/me/favorites/products/{product_id}",
            headers=registered_user["headers"],
        )
        assert delete_response.status_code == 204, delete_response.text

        out_of_stock_subscription = _get_stock_subscription(registered_user["user_id"], variant_ids[0])
        low_stock_subscription = _get_stock_subscription(registered_user["user_id"], variant_ids[1])
        assert out_of_stock_subscription is not None
        assert out_of_stock_subscription.is_active is False
        assert low_stock_subscription is not None
        assert low_stock_subscription.is_active is False
    finally:
        _delete_product(product_id)


def test_delete_stock_subscription_soft_disables(client: TestClient, registered_user):
    catalog = _create_product_variant(stock=0, price=_decimal("11.00"))

    try:
        create_response = client.post(
            "/api/v1/users/me/stock-subscriptions",
            headers=registered_user["headers"],
            json={"variant_id": catalog["variant_id"]},
        )
        assert create_response.status_code == 200, create_response.text

        delete_response = client.delete(
            f"/api/v1/users/me/stock-subscriptions/{catalog['variant_id']}",
            headers=registered_user["headers"],
        )
        assert delete_response.status_code == 200, delete_response.text
        assert delete_response.json() == {"ok": True}

        subscription = _get_stock_subscription(registered_user["user_id"], catalog["variant_id"])
        assert subscription is not None
        assert subscription.is_active is False
    finally:
        _delete_product(catalog["product_id"])
