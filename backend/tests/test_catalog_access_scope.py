import uuid

import config
import pytest

from test_products_advanced_search_api import _seed_search_products, _cleanup_seed, sync_engine


@pytest.fixture
def scoped_catalog(monkeypatch, register_verified_user):
    seed = _seed_search_products()
    accounts = []
    for label in ("limited", "regular"):
        accounts.append(register_verified_user({
            "email": f"catalog-{label}-{uuid.uuid4().hex}@example.com",
            "password": "TestCatalog123!",
            "name": "Catalog",
            "surname": "Test",
        }))
    limited, regular = accounts
    seed["limited"] = {"Authorization": f"Bearer {limited['access_token']}"}
    seed["regular"] = {"Authorization": f"Bearer {regular['access_token']}"}
    seed["limited_id"] = limited["user"]["id"]
    seed["regular_id"] = regular["user"]["id"]
    try:
        yield seed
    finally:
        _cleanup_seed(seed)


@pytest.mark.parametrize("identity", ["guest", "limited", "regular"])
@pytest.mark.parametrize("platform", ["ios", "android", "web"])
def test_every_customer_and_guest_sees_the_full_published_catalog(client, scoped_catalog, identity, platform):
    s = scoped_catalog
    headers = {**s.get(identity, {}), "X-App-Platform": platform}
    expected = {s["ru_product_id"], s["en_product_id"], s["noise_product_id"]}
    response = client.get("/api/v1/products?limit=100", headers=headers)
    assert response.status_code == 200, response.text
    assert expected <= {row["id"] for row in response.json()}
    for product_id in expected:
        assert client.get(f"/api/v1/products/{product_id}", headers=headers).status_code == 200
    categories = client.get("/api/v1/product-categories", headers=headers)
    assert categories.status_code == 200
    assert {s["accessories_category_id"], s["peptides_category_id"]} <= {row["id"] for row in categories.json()}
    assert response.headers["cache-control"] == "no-store"


def test_invalid_token_is_rejected_even_though_the_catalog_is_public(client, scoped_catalog):
    for path in ("products", "product-categories", "banners"):
        response = client.get(f"/api/v1/{path}", headers={"Authorization": "Bearer invalid"})
        assert response.status_code == 401


@pytest.mark.parametrize("identity", ["guest", "limited", "regular"])
def test_guests_and_customers_can_quote_every_published_category(client, scoped_catalog, identity):
    s = scoped_catalog
    headers = {**s.get(identity, {}), "X-App-Platform": "ios"}
    product = client.get(f"/api/v1/products/{s['ru_product_id']}", headers=headers).json()
    variant_id = product["variants"][0]["id"]
    response = client.post("/api/v1/guest/basket/quote", headers=headers,
                           json={"items": [{"variant_id": variant_id, "quantity": 1}]})
    assert response.status_code == 200, response.text
    assert response.json()["total_quantity"] == 1


def test_unknown_product_does_not_become_visible_when_scopes_are_removed(client):
    assert client.get("/api/v1/products/999999999", headers={"X-App-Platform": "ios"}).status_code == 404
