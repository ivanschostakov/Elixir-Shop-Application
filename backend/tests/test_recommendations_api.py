import sys
import types
import uuid

from datetime import timedelta
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

from config import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER, ufa_now
from src.database.models import (
    FavouredProduct,
    Product,
    ProductByCategory,
    ProductCategory,
    ReferralProfile,
    UserCategoryRecommendationSignal,
    User,
    UserProductRecommendationSignal,
    Variant,
    WebsiteDiscountEntitlement,
    WebsiteIdentity,
)

SYNC_DB_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
sync_engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)


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


def _delete_category(category_id: int) -> None:
    with Session(sync_engine) as session:
        category = session.get(ProductCategory, category_id)
        if category is None:
            return
        session.delete(category)
        session.commit()


def _create_category(name_prefix: str) -> int:
    token = uuid.uuid4().hex[:12]
    with Session(sync_engine) as session:
        category = ProductCategory(
            name=f"{name_prefix}-{token}",
            description=None,
        )
        session.add(category)
        session.commit()
        session.refresh(category)
        return int(category.id)


def _create_product_variant(
    *,
    category_ids: list[int],
    stock: int = 5,
    price: Decimal = Decimal("10.00"),
    priority: int = 0,
) -> dict[str, int]:
    token = uuid.uuid4().hex
    with Session(sync_engine) as session:
        product = Product(
            sku=f"rec-sku-{token[:20]}",
            name=f"Recommendations Product {token[:12]}",
            description=None,
            usage=None,
            expiration=None,
            in_stock=stock > 0,
            priority=priority,
        )
        session.add(product)
        session.flush()

        variant = Variant(
            product_id=product.id,
            sku=f"rec-var-{token[:20]}",
            name=f"Recommendations Variant {token[:8]}",
            stock=stock,
            price=price,
        )
        session.add(variant)
        session.flush()

        for category_id in category_ids:
            session.add(ProductByCategory(product_id=product.id, category_id=category_id))

        session.commit()
        session.refresh(product)
        session.refresh(variant)
        return {"product_id": int(product.id), "variant_id": int(variant.id)}


def _get_signal(user_id: int, product_id: int) -> UserProductRecommendationSignal | None:
    with Session(sync_engine) as session:
        stmt = select(UserProductRecommendationSignal).where(
            UserProductRecommendationSignal.user_id == user_id,
            UserProductRecommendationSignal.product_id == product_id,
        )
        return session.execute(stmt).scalar_one_or_none()


def _get_category_signal(user_id: int, category_id: int) -> UserCategoryRecommendationSignal | None:
    with Session(sync_engine) as session:
        stmt = select(UserCategoryRecommendationSignal).where(
            UserCategoryRecommendationSignal.user_id == user_id,
            UserCategoryRecommendationSignal.category_id == category_id,
        )
        return session.execute(stmt).scalar_one_or_none()


def _get_favourite(user_id: int, product_id: int) -> FavouredProduct | None:
    with Session(sync_engine) as session:
        stmt = select(FavouredProduct).where(
            FavouredProduct.user_id == user_id,
            FavouredProduct.product_id == product_id,
        )
        return session.execute(stmt).scalar_one_or_none()


def _update_signal_timestamps(
    user_id: int,
    product_id: int,
    *,
    last_viewed_at=None,
    last_carted_at=None,
    last_purchased_at=None,
) -> None:
    with Session(sync_engine) as session:
        stmt = select(UserProductRecommendationSignal).where(
            UserProductRecommendationSignal.user_id == user_id,
            UserProductRecommendationSignal.product_id == product_id,
        )
        signal = session.execute(stmt).scalar_one()
        if last_viewed_at is not None:
            signal.last_viewed_at = last_viewed_at
        if last_carted_at is not None:
            signal.last_carted_at = last_carted_at
        if last_purchased_at is not None:
            signal.last_purchased_at = last_purchased_at
        session.commit()


def _update_category_signal_timestamp(
    user_id: int,
    category_id: int,
    *,
    last_viewed_at,
) -> None:
    with Session(sync_engine) as session:
        stmt = select(UserCategoryRecommendationSignal).where(
            UserCategoryRecommendationSignal.user_id == user_id,
            UserCategoryRecommendationSignal.category_id == category_id,
        )
        signal = session.execute(stmt).scalar_one()
        signal.last_viewed_at = last_viewed_at
        session.commit()


def _seed_product_price_discount_context(user_id: int) -> None:
    token = uuid.uuid4().int % 100000000
    with Session(sync_engine) as session:
        website_identity = WebsiteIdentity(
            user_id=user_id,
            website_user_id=800000000 + token,
            website_login=f"price-site-{token}",
            website_email=None,
        )
        session.add(website_identity)
        session.flush()

        session.add(
            ReferralProfile(
                user_id=user_id,
                website_identity_id=website_identity.id,
                referrer_promo_code="SITE",
                website_seed_purchase_balance=Decimal("150000.00"),
                app_paid_purchase_total=Decimal("40000.00"),
                referral_discount_base_total=Decimal("190000.00"),
                current_discount_percent=Decimal("19.00"),
                website_seeded_at=ufa_now(),
            )
        )
        session.add(
            WebsiteDiscountEntitlement(
                website_identity_id=website_identity.id,
                source_kind="group",
                website_source_id="vip",
                source_name="VIP",
                discount_percent=Decimal("5.00"),
                currency="RUB",
                is_active=True,
                is_stackable=True,
            )
        )
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


def _create_ready_draft(client: TestClient, headers: dict[str, str], variant_id: int) -> dict:
    basket_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=headers,
        json={"variant_id": variant_id, "quantity": 1},
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


@pytest.fixture()
def registered_user(register_verified_user):
    token = uuid.uuid4().hex[:12]
    payload = register_verified_user({
        "username": f"u{token}",
        "email": f"recommendations_{token}@example.com",
        "password": "test-password",
        "name": "Recommendations",
        "surname": "Tester",
    })
    user_id = payload["user"]["id"]

    try:
        yield {"user_id": user_id, "headers": {"Authorization": f"Bearer {payload['access_token']}"}}
    finally:
        _delete_user(user_id)


@pytest.fixture()
def category_factory():
    created_category_ids: list[int] = []

    def _factory(name_prefix: str) -> int:
        category_id = _create_category(name_prefix)
        created_category_ids.append(category_id)
        return category_id

    try:
        yield _factory
    finally:
        for category_id in reversed(created_category_ids):
            _delete_category(category_id)


@pytest.fixture()
def product_factory():
    created_product_ids: list[int] = []

    def _factory(
        *,
        category_ids: list[int],
        stock: int = 5,
        price: Decimal = Decimal("10.00"),
        priority: int = 0,
    ) -> dict[str, int]:
        payload = _create_product_variant(
            category_ids=category_ids,
            stock=stock,
            price=price,
            priority=priority,
        )
        created_product_ids.append(payload["product_id"])
        return payload

    try:
        yield _factory
    finally:
        for product_id in reversed(created_product_ids):
            _delete_product(product_id)


@pytest.fixture()
def stub_amocrm(monkeypatch):
    async def fake_find_lead_by_order_number(order_number):
        return None

    async def fake_find_or_create_contact(**kwargs):
        return {"id": 12345}

    async def fake_create_lead_with_contact_and_note(**kwargs):
        return {"id": 67890}

    async def fake_update_lead_status(lead_id, status_id):
        return {"id": lead_id, "status_id": status_id}

    monkeypatch.setattr("src.app.services.orders.amocrm_client.find_lead_by_order_number", fake_find_lead_by_order_number)
    monkeypatch.setattr("src.app.services.orders.amocrm_client.find_or_create_contact", fake_find_or_create_contact)
    monkeypatch.setattr("src.app.services.orders.amocrm_client.create_lead_with_contact_and_note", fake_create_lead_with_contact_and_note)
    monkeypatch.setattr("src.app.services.orders.amocrm_client.update_lead_status", fake_update_lead_status)


def test_create_recommendation_view_dedupes_within_30_minutes(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
):
    category_id = category_factory("view-dedupe")
    catalog = product_factory(category_ids=[category_id])

    first_response = client.post(
        "/api/v1/users/me/recommendations/views",
        headers=registered_user["headers"],
        json={"product_id": catalog["product_id"], "variant_id": catalog["variant_id"]},
    )
    assert first_response.status_code == 204, first_response.text

    second_response = client.post(
        "/api/v1/users/me/recommendations/views",
        headers=registered_user["headers"],
        json={"product_id": catalog["product_id"]},
    )
    assert second_response.status_code == 204, second_response.text

    signal = _get_signal(registered_user["user_id"], catalog["product_id"])
    assert signal is not None
    assert signal.view_count == 1

    _update_signal_timestamps(
        registered_user["user_id"],
        catalog["product_id"],
        last_viewed_at=ufa_now() - timedelta(minutes=31),
    )

    third_response = client.post(
        "/api/v1/users/me/recommendations/views",
        headers=registered_user["headers"],
        json={"product_id": catalog["product_id"]},
    )
    assert third_response.status_code == 204, third_response.text

    refreshed_signal = _get_signal(registered_user["user_id"], catalog["product_id"])
    assert refreshed_signal is not None
    assert refreshed_signal.view_count == 2


def test_create_category_recommendation_view_dedupes_within_30_minutes(
    client: TestClient,
    registered_user,
    category_factory,
):
    category_id = category_factory("category-view-dedupe")

    first_response = client.post(
        "/api/v1/users/me/recommendations/categories/views",
        headers=registered_user["headers"],
        json={"category_id": category_id},
    )
    assert first_response.status_code == 204, first_response.text

    second_response = client.post(
        "/api/v1/users/me/recommendations/categories/views",
        headers=registered_user["headers"],
        json={"category_id": category_id},
    )
    assert second_response.status_code == 204, second_response.text

    signal = _get_category_signal(registered_user["user_id"], category_id)
    assert signal is not None
    assert signal.view_count == 1

    _update_category_signal_timestamp(
        registered_user["user_id"],
        category_id,
        last_viewed_at=ufa_now() - timedelta(minutes=31),
    )

    third_response = client.post(
        "/api/v1/users/me/recommendations/categories/views",
        headers=registered_user["headers"],
        json={"category_id": category_id},
    )
    assert third_response.status_code == 204, third_response.text

    refreshed_signal = _get_category_signal(registered_user["user_id"], category_id)
    assert refreshed_signal is not None
    assert refreshed_signal.view_count == 2


def test_recommendation_signals_record_cart_adds_and_purchases(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
    stub_amocrm,
):
    category_id = category_factory("cart-purchase")
    catalog = product_factory(category_ids=[category_id], price=Decimal("12.50"))

    add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": catalog["variant_id"], "quantity": 2},
    )
    assert add_response.status_code == 200, add_response.text
    item_id = add_response.json()["items"][0]["id"]

    signal_after_add = _get_signal(registered_user["user_id"], catalog["product_id"])
    assert signal_after_add is not None
    assert signal_after_add.cart_quantity == 2
    assert signal_after_add.purchase_quantity == 0

    update_response = client.patch(
        f"/api/v1/users/me/basket/items/{item_id}",
        headers=registered_user["headers"],
        json={"quantity": 5},
    )
    assert update_response.status_code == 200, update_response.text

    signal_after_increase = _get_signal(registered_user["user_id"], catalog["product_id"])
    assert signal_after_increase is not None
    assert signal_after_increase.cart_quantity == 5

    draft_response = client.post(
        "/api/v1/users/me/order-drafts",
        headers=registered_user["headers"],
        json=_build_pickup_payload(),
    )
    assert draft_response.status_code == 201, draft_response.text
    draft = draft_response.json()

    recipient_response = client.patch(
        f"/api/v1/users/me/order-drafts/{draft['id']}",
        headers=registered_user["headers"],
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

    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "later"},
    )
    assert order_response.status_code == 200, order_response.text

    signal_after_purchase = _get_signal(registered_user["user_id"], catalog["product_id"])
    assert signal_after_purchase is not None
    assert signal_after_purchase.cart_quantity == 5
    assert signal_after_purchase.purchase_quantity == 5


def test_home_recommendations_rank_purchase_above_cart_above_view(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
    stub_amocrm,
):
    purchase_category_id = category_factory("purchase-rank")
    cart_category_id = category_factory("cart-rank")
    view_category_id = category_factory("view-rank")

    purchased_source = product_factory(category_ids=[purchase_category_id], price=Decimal("15.00"))
    purchased_candidate = product_factory(category_ids=[purchase_category_id], price=Decimal("16.00"))
    cart_source = product_factory(category_ids=[cart_category_id], price=Decimal("11.00"))
    cart_candidate = product_factory(category_ids=[cart_category_id], price=Decimal("12.00"))
    viewed_source = product_factory(category_ids=[view_category_id], price=Decimal("7.00"))
    viewed_candidate = product_factory(category_ids=[view_category_id], price=Decimal("8.00"))

    view_response = client.post(
        "/api/v1/users/me/recommendations/views",
        headers=registered_user["headers"],
        json={"product_id": viewed_source["product_id"]},
    )
    assert view_response.status_code == 204, view_response.text

    cart_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": cart_source["variant_id"], "quantity": 1},
    )
    assert cart_response.status_code == 200, cart_response.text

    purchase_draft = _create_ready_draft(client, registered_user["headers"], purchased_source["variant_id"])
    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": purchase_draft["id"], "payment_method": "later"},
    )
    assert order_response.status_code == 200, order_response.text

    response = client.get(
        "/api/v1/users/me/recommendations",
        headers=registered_user["headers"],
        params={"surface": "home", "limit": 3},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert [item["id"] for item in payload[:3]] == [
        purchased_candidate["product_id"],
        cart_candidate["product_id"],
        viewed_candidate["product_id"],
    ]


def test_home_recommendations_include_favourite_categories(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
):
    favourite_category_id = category_factory("favorite-affinity")
    other_category_id = category_factory("other-affinity")

    favourite_source = product_factory(category_ids=[favourite_category_id], priority=0)
    favourite_candidate = product_factory(category_ids=[favourite_category_id], priority=5)
    other_candidate = product_factory(category_ids=[other_category_id], priority=9)

    favourite_response = client.post(
        f"/api/v1/users/me/favorites/products/{favourite_source['product_id']}",
        headers=registered_user["headers"],
    )
    assert favourite_response.status_code == 201, favourite_response.text
    assert _get_favourite(registered_user["user_id"], favourite_source["product_id"]) is not None

    response = client.get(
        "/api/v1/users/me/recommendations",
        headers=registered_user["headers"],
        params={"surface": "home", "limit": 3},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    product_ids = [item["id"] for item in payload]
    assert favourite_candidate["product_id"] in product_ids
    assert other_candidate["product_id"] not in product_ids


def test_home_recommendations_include_viewed_categories(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
):
    viewed_category_id = category_factory("category-affinity")
    other_category_id = category_factory("category-other")

    top_candidate = product_factory(category_ids=[viewed_category_id], priority=5)
    second_candidate = product_factory(category_ids=[viewed_category_id], priority=2)
    other_candidate = product_factory(category_ids=[other_category_id], priority=9)

    category_response = client.post(
        "/api/v1/users/me/recommendations/categories/views",
        headers=registered_user["headers"],
        json={"category_id": viewed_category_id},
    )
    assert category_response.status_code == 204, category_response.text

    response = client.get(
        "/api/v1/users/me/recommendations",
        headers=registered_user["headers"],
        params={"surface": "home", "limit": 3},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert [item["id"] for item in payload[:2]] == [
        top_candidate["product_id"],
        second_candidate["product_id"],
    ]
    assert other_candidate["product_id"] not in {item["id"] for item in payload}


def test_product_recommendations_rank_more_shared_categories_higher(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
):
    primary_category_id = category_factory("product-overlap-primary")
    secondary_category_id = category_factory("product-overlap-secondary")

    current_product = product_factory(category_ids=[primary_category_id, secondary_category_id], price=Decimal("10.00"))
    broad_match = product_factory(category_ids=[primary_category_id, secondary_category_id], price=Decimal("11.00"))
    narrow_match = product_factory(category_ids=[primary_category_id], price=Decimal("12.00"))

    response = client.get(
        "/api/v1/users/me/recommendations",
        headers=registered_user["headers"],
        params={"surface": "product", "product_id": current_product["product_id"], "limit": 2},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert [item["id"] for item in payload[:2]] == [
        broad_match["product_id"],
        narrow_match["product_id"],
    ]


def test_product_similarity_ranks_by_shared_categories(
    client: TestClient,
    category_factory,
    product_factory,
):
    primary_category_id = category_factory("similar-overlap-primary")
    secondary_category_id = category_factory("similar-overlap-secondary")
    other_category_id = category_factory("similar-overlap-other")

    current_product = product_factory(category_ids=[primary_category_id, secondary_category_id], price=Decimal("10.00"))
    broad_match = product_factory(
        category_ids=[primary_category_id, secondary_category_id, other_category_id],
        price=Decimal("11.00"),
    )
    narrow_match = product_factory(category_ids=[primary_category_id], price=Decimal("12.00"))
    unrelated_product = product_factory(category_ids=[other_category_id], price=Decimal("13.00"))

    response = client.get(f"/api/v1/products/{current_product['product_id']}/similar", params={"limit": 6})
    assert response.status_code == 200, response.text

    payload = response.json()
    product_ids = [item["id"] for item in payload]
    assert product_ids[:2] == [
        broad_match["product_id"],
        narrow_match["product_id"],
    ]
    assert current_product["product_id"] not in product_ids
    assert unrelated_product["product_id"] not in product_ids


def test_product_detail_returns_user_discounted_variant_price(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
):
    category_id = category_factory("price-preview")
    catalog = product_factory(category_ids=[category_id], price=Decimal("1000.00"))
    _seed_product_price_discount_context(registered_user["user_id"])

    anonymous_response = client.get(f"/api/v1/products/{catalog['product_id']}")
    assert anonymous_response.status_code == 200, anonymous_response.text
    anonymous_variant = anonymous_response.json()["variants"][0]
    assert Decimal(str(anonymous_variant["price"])) == Decimal("1000.00")
    assert Decimal(str(anonymous_variant["original_price"])) == Decimal("1000.00")
    assert Decimal(str(anonymous_variant["discounted_price"])) == Decimal("1000.00")
    assert Decimal(str(anonymous_variant["discount_percent"])) == Decimal("0.00")

    response = client.get(f"/api/v1/products/{catalog['product_id']}", headers=registered_user["headers"])
    assert response.status_code == 200, response.text
    variant = response.json()["variants"][0]
    assert Decimal(str(variant["price"])) == Decimal("1000.00")
    assert Decimal(str(variant["original_price"])) == Decimal("1000.00")
    assert Decimal(str(variant["discounted_price"])) == Decimal("769.50")
    assert Decimal(str(variant["discount_percent"])) == Decimal("23.05")


def test_product_similarity_excludes_out_of_stock_products(
    client: TestClient,
    category_factory,
    product_factory,
):
    category_id = category_factory("similar-in-stock")

    current_product = product_factory(category_ids=[category_id], price=Decimal("10.00"))
    in_stock_candidate = product_factory(category_ids=[category_id], price=Decimal("11.00"))
    product_factory(category_ids=[category_id], stock=0, price=Decimal("12.00"))

    response = client.get(f"/api/v1/products/{current_product['product_id']}/similar", params={"limit": 6})
    assert response.status_code == 200, response.text

    payload = response.json()
    product_ids = {item["id"] for item in payload}
    assert current_product["product_id"] not in product_ids
    assert in_stock_candidate["product_id"] in product_ids
    assert len(product_ids) == 1


def test_product_recommendations_exclude_current_product(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
):
    category_id = category_factory("product-surface")
    current_product = product_factory(category_ids=[category_id], price=Decimal("10.00"))
    candidate_product = product_factory(category_ids=[category_id], price=Decimal("12.00"))

    response = client.get(
        "/api/v1/users/me/recommendations",
        headers=registered_user["headers"],
        params={"surface": "product", "product_id": current_product["product_id"], "limit": 6},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    product_ids = {item["id"] for item in payload}
    assert current_product["product_id"] not in product_ids
    assert candidate_product["product_id"] in product_ids


def test_cart_recommendations_exclude_items_already_in_basket(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
):
    category_id = category_factory("cart-surface")
    basket_product = product_factory(category_ids=[category_id], price=Decimal("9.00"))
    candidate_product = product_factory(category_ids=[category_id], price=Decimal("13.00"))

    add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": basket_product["variant_id"], "quantity": 1},
    )
    assert add_response.status_code == 200, add_response.text

    response = client.get(
        "/api/v1/users/me/recommendations",
        headers=registered_user["headers"],
        params={"surface": "cart", "limit": 6},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    product_ids = {item["id"] for item in payload}
    assert basket_product["product_id"] not in product_ids
    assert candidate_product["product_id"] in product_ids


def test_cart_recommendations_include_viewed_product_categories(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
):
    basket_category_id = category_factory("cart-basket-category")
    viewed_category_id = category_factory("cart-viewed-category")

    basket_product = product_factory(category_ids=[basket_category_id], price=Decimal("9.00"))
    basket_candidate = product_factory(category_ids=[basket_category_id], price=Decimal("13.00"))
    viewed_source = product_factory(category_ids=[viewed_category_id], price=Decimal("7.00"))
    viewed_candidate = product_factory(category_ids=[viewed_category_id], price=Decimal("8.00"))

    add_response = client.post(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
        json={"variant_id": basket_product["variant_id"], "quantity": 1},
    )
    assert add_response.status_code == 200, add_response.text

    view_response = client.post(
        "/api/v1/users/me/recommendations/views",
        headers=registered_user["headers"],
        json={"product_id": viewed_source["product_id"]},
    )
    assert view_response.status_code == 204, view_response.text

    response = client.get(
        "/api/v1/users/me/recommendations",
        headers=registered_user["headers"],
        params={"surface": "cart", "limit": 6},
    )
    assert response.status_code == 200, response.text

    product_ids = {item["id"] for item in response.json()}
    assert basket_product["product_id"] not in product_ids
    assert basket_candidate["product_id"] in product_ids
    assert viewed_candidate["product_id"] in product_ids


def test_draft_recommendations_exclude_items_already_in_draft(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
):
    category_id = category_factory("draft-surface")
    draft_product = product_factory(category_ids=[category_id], price=Decimal("14.00"))
    candidate_product = product_factory(category_ids=[category_id], price=Decimal("15.00"))

    draft = _create_ready_draft(client, registered_user["headers"], draft_product["variant_id"])

    response = client.get(
        "/api/v1/users/me/recommendations",
        headers=registered_user["headers"],
        params={"surface": "draft", "draft_id": draft["id"], "limit": 6},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    product_ids = {item["id"] for item in payload}
    assert draft_product["product_id"] not in product_ids
    assert candidate_product["product_id"] in product_ids


def test_home_recommendations_exclude_recently_purchased_products(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
    stub_amocrm,
):
    category_id = category_factory("recent-purchase")
    purchased_product = product_factory(category_ids=[category_id], price=Decimal("18.00"))
    candidate_product = product_factory(category_ids=[category_id], price=Decimal("19.00"))

    draft = _create_ready_draft(client, registered_user["headers"], purchased_product["variant_id"])
    order_response = client.post(
        "/api/v1/users/me/orders",
        headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "later"},
    )
    assert order_response.status_code == 200, order_response.text

    clear_response = client.delete(
        "/api/v1/users/me/basket/items",
        headers=registered_user["headers"],
    )
    assert clear_response.status_code == 200, clear_response.text

    response = client.get(
        "/api/v1/users/me/recommendations",
        headers=registered_user["headers"],
        params={"surface": "home", "limit": 6},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    product_ids = {item["id"] for item in payload}
    assert purchased_product["product_id"] not in product_ids
    assert candidate_product["product_id"] in product_ids


def test_home_recommendations_fall_back_to_newest_products_without_affinity(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
):
    category_id = category_factory("home-fallback")
    older_product = product_factory(category_ids=[category_id], priority=9)
    newer_product = product_factory(category_ids=[category_id], priority=1)
    newest_product = product_factory(category_ids=[category_id], priority=0)

    response = client.get(
        "/api/v1/users/me/recommendations",
        headers=registered_user["headers"],
        params={"surface": "home", "limit": 2},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert [item["id"] for item in payload] == [
        newest_product["product_id"],
        newer_product["product_id"],
    ]


def test_home_recommendations_support_offset_pagination(
    client: TestClient,
    registered_user,
    category_factory,
    product_factory,
):
    category_id = category_factory("pagination-home")
    viewed_source = product_factory(category_ids=[category_id], price=Decimal("8.00"))
    first_candidate = product_factory(category_ids=[category_id], price=Decimal("9.00"))
    second_candidate = product_factory(category_ids=[category_id], price=Decimal("10.00"))
    third_candidate = product_factory(category_ids=[category_id], price=Decimal("11.00"))

    view_response = client.post(
        "/api/v1/users/me/recommendations/views",
        headers=registered_user["headers"],
        json={"product_id": viewed_source["product_id"]},
    )
    assert view_response.status_code == 204, view_response.text

    first_page_response = client.get(
        "/api/v1/users/me/recommendations",
        headers=registered_user["headers"],
        params={"surface": "home", "limit": 2, "offset": 0},
    )
    assert first_page_response.status_code == 200, first_page_response.text

    second_page_response = client.get(
        "/api/v1/users/me/recommendations",
        headers=registered_user["headers"],
        params={"surface": "home", "limit": 2, "offset": 2},
    )
    assert second_page_response.status_code == 200, second_page_response.text

    first_page_ids = [item["id"] for item in first_page_response.json()]
    second_page_ids = [item["id"] for item in second_page_response.json()]

    assert first_page_ids == [
        third_candidate["product_id"],
        second_candidate["product_id"],
    ]
    assert second_page_ids == [first_candidate["product_id"]]
