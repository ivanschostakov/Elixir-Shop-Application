import uuid
from datetime import timedelta

import config
import pytest
from sqlalchemy.orm import Session

from src.database.models import Banner, FavouredProduct, ProductByCategory
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
    monkeypatch.setattr(config, "CATALOG_ACCESSORY_CATEGORY_ID", seed["accessories_category_id"])
    monkeypatch.setattr(config, "CATALOG_ACCESSORY_ONLY_USER_IDS", [str(limited["user"]["id"])])
    monkeypatch.setattr(config, "CATALOG_GUEST_ACCESSORIES_ONLY", True)
    monkeypatch.setattr(config, "APPLE_DEV_MODE", True)
    seed["limited"] = {"Authorization": f"Bearer {limited['access_token']}"}
    seed["regular"] = {"Authorization": f"Bearer {regular['access_token']}"}
    seed["limited_id"] = limited["user"]["id"]
    try:
        yield seed
    finally:
        _cleanup_seed(seed)


@pytest.mark.parametrize("identity", ["guest", "limited"])
@pytest.mark.parametrize("platform", ["ios", "android", "web"])
def test_restricted_catalog_and_direct_links(client, scoped_catalog, identity, platform):
    s = scoped_catalog
    headers = {**s.get(identity, {}), "X-App-Platform": platform}
    allowed = {s["en_product_id"], s["noise_product_id"]}
    products = client.get("/api/v1/products?limit=100", headers=headers)
    assert products.status_code == 200, products.text
    assert {p["id"] for p in products.json()} == allowed
    assert "Authorization" in products.headers["vary"]
    assert products.headers["cache-control"] == "no-store"
    categories = client.get("/api/v1/product-categories", headers=headers)
    assert [c["id"] for c in categories.json()] == [s["accessories_category_id"]]
    assert client.get("/api/v1/banners", headers=headers).json() == []
    hidden = s["ru_product_id"]
    for suffix in ("", "/similar", "/reviews", "/reviews/eligibility", "/questions"):
        r = client.get(f"/api/v1/products/{hidden}{suffix}", headers=headers)
        assert r.status_code == 404, (suffix, r.text)
    assert client.get(f"/api/v1/products/{s['en_product_id']}", headers=headers).status_code == 200
    for params in ({"sku": s["ru_product_sku"]}, {"category_id": s["peptides_category_id"]}):
        assert client.get("/api/v1/products", params=params, headers=headers).json() == []
    pages = [client.get("/api/v1/products", params={"limit": 1, "offset": n}, headers=headers).json() for n in (0, 1, 2)]
    assert {p["id"] for page in pages for p in page} == allowed
    assert [len(page) for page in pages] == [1, 1, 0]


def test_cache_scope_and_regular_customer_unchanged(client, scoped_catalog):
    s = scoped_catalog
    url = f"/api/v1/products/{s['ru_product_id']}"
    # Full customer reads must not leak into subsequent anonymous reads.
    assert client.get(url, headers=s["regular"]).status_code == 200
    assert client.get(url).status_code == 404
    for headers in (s["regular"], {}, s["limited"], s["regular"]):
        categories = client.get("/api/v1/product-categories", headers=headers).json()
        ids = {c["id"] for c in categories}
        assert (s["peptides_category_id"] in ids) == (headers == s["regular"])
    normal_ios = {**s["regular"], "X-App-Platform": "ios"}
    assert client.get("/api/v1/products", headers=normal_ios).json() == []
    assert client.get(url, headers=normal_ios).status_code == 404
    # This feature opens catalog reads only, not purchases or chat on iOS.
    assert client.post("/api/v1/guest/orders", headers={"X-App-Platform": "ios"}, json={}).status_code == 403


def test_invalid_token_does_not_get_full_catalog(client, scoped_catalog):
    for path in ("products", "product-categories", "banners"):
        response = client.get(f"/api/v1/{path}", headers={"Authorization": "Bearer invalid"})
        assert response.status_code == 401


def test_similar_favorites_recommendations_stay_in_scope(client, scoped_catalog):
    s = scoped_catalog
    with Session(sync_engine) as db:
        # Mixed category membership must not bring unrelated products back.
        db.add(ProductByCategory(product_id=s["en_product_id"], category_id=s["peptides_category_id"]))
        db.add(FavouredProduct(user_id=s["limited_id"], product_id=s["ru_product_id"]))
        db.add(FavouredProduct(user_id=s["limited_id"], product_id=s["en_product_id"]))
        db.commit()
    allowed = {s["en_product_id"], s["noise_product_id"]}
    for headers in ({}, s["limited"]):
        response = client.get(f"/api/v1/products/{s['en_product_id']}/similar", headers=headers)
        assert response.status_code == 200, response.text
        assert {p["id"] for p in response.json()} == {s["noise_product_id"]}
    for path in ("/api/v1/favorites/products", "/api/v1/users/me/recommendations?surface=home"):
        response = client.get(path, headers=s["limited"])
        assert response.status_code == 200, response.text
        assert response.json()
        assert {p["id"] for p in response.json()} <= allowed
    assert client.post(f"/api/v1/favorites/products/{s['ru_product_id']}", headers=s["limited"]).status_code == 404


def test_guest_quote_cannot_reveal_hidden_product(client, scoped_catalog):
    s = scoped_catalog
    product = client.get(f"/api/v1/products/{s['ru_product_id']}", headers=s["regular"]).json()
    variant_id = product["variants"][0]["id"]
    response = client.post("/api/v1/guest/basket/quote", json={"items": [{"variant_id": variant_id, "quantity": 1}]})
    assert response.status_code == 404, response.text


def test_neutral_welcome_banner_is_visible_without_product_leaks(client, scoped_catalog):
    token = uuid.uuid4().hex
    now = config.ufa_now()
    banners = []
    for name, changes in (
        ("welcome", {}),
        ("product", {"audience_json": {}}),
        ("product-link", {"inner_link": "/products/148"}),
        ("external", {"outer_link": "https://example.com"}),
        ("draft", {"status": "draft"}),
        ("future", {"starts_at": now + timedelta(days=1)}),
        ("expired", {"ends_at": now - timedelta(days=1)}),
        ("archived", {"archived": True}),
    ):
        data = dict(image_path=f"/media/banners/{token}-{name}.png", title=name,
                    inner_link="/discover?tab=products", audience_json={"catalog_scope": "all"},
                    priority=100 if name == "welcome" else 200, status="published", archived=False)
        data.update(changes)
        banners.append(Banner(**data))
    with Session(sync_engine) as db:
        db.add_all(banners)
        db.flush()
        ids = [banner.id for banner in banners]
        db.commit()
    try:
        regular = client.get("/api/v1/banners?limit=50", headers=scoped_catalog["regular"])
        assert regular.status_code == 200, regular.text
        assert {row["id"] for row in regular.json()} == set(ids[:4])
        for headers in ({}, scoped_catalog["limited"], {**scoped_catalog["regular"], "X-App-Platform": "ios"}):
            for query in ("?limit=50", "?limit=1&sort=priority_desc"):
                response = client.get("/api/v1/banners" + query, headers=headers)
                assert response.status_code == 200, response.text
                assert [row["id"] for row in response.json()] == [ids[0]]
                assert response.json()[0]["inner_link"] == "/discover?tab=products"
            assert client.get("/api/v1/banners?limit=1&offset=1", headers=headers).json() == []
            assert client.get(f"/api/v1/products/{scoped_catalog['ru_product_id']}", headers=headers).status_code == 404
    finally:
        with Session(sync_engine) as db:
            db.query(Banner).filter(Banner.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
