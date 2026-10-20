"""Public visibility uses real SQL, including pagination and account scopes."""

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request
from unittest.mock import Mock

from src.app.modules.auth.dependencies import get_optional_current_user
from src.app.modules.products.access import get_catalog_scope, require_visible_product
from src.app.modules.products import router as products_router
from src.app.modules.users.me.promotions import list_my_promotions
from src.database import get_db
from src.database.crud.catalog.product import (
    get_product_by_id,
    get_products,
    get_priority_products,
    get_similar_products,
)
from src.database.crud.catalog.products_by_category import get_products_for_category
from src.database.crud.favorites.favoured_product import get_favourite_products_for_user
from src.database.crud.recommendations import (
    get_candidate_products_for_categories,
    get_home_fallback_products,
)
from src.database.models import (
    FavouredProduct,
    Product,
    ProductByCategory,
    ProductCategory,
    ProductCertificate,
    Variant,
)


class AsyncSessionAdapter:
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def scalar(self, statement):
        return self.session.scalar(statement)


@pytest.fixture
def catalog():
    engine = create_engine("sqlite://")
    for model in (Product, Variant, ProductCategory, ProductByCategory, ProductCertificate, FavouredProduct):
        model.__table__.create(engine)
    with Session(engine) as session:
        session.add(ProductCategory(id=1, name="Category"))
        # The hidden item would sort ahead of the visible item without the filter.
        for product_id, visible in ((1, True), (2, False)):
            session.add(Product(
                id=product_id,
                sku=f"shared-{product_id}",
                name=f"Shared product {product_id}",
                in_stock=True,
                is_visible_in_app=visible,
                is_new_manual=True,
                priority=10,
            ))
            session.add(Variant(
                id=product_id, product_id=product_id, name="Variant", stock=10, price=100,
            ))
            session.add(ProductByCategory(id=product_id, product_id=product_id, category_id=1))
            session.add(FavouredProduct(id=product_id, user_id=1, product_id=product_id))
        session.commit()
        yield AsyncSessionAdapter(session)
    engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("filters", [
    {}, {"q": "shared"}, {"sku": "shared-2"}, {"category_id": 1},
    {"new_only": True}, {"min_priority": 1}, {"allowed_category_ids": (1,)},
    {"include_archived": True},
])
async def test_hidden_products_are_excluded_before_catalog_pagination(catalog, filters):
    first_page = await get_products(catalog, limit=1, **filters)
    second_page = await get_products(catalog, limit=1, offset=1, **filters)
    assert [product.id for product in first_page] == ([] if "sku" in filters else [1])
    assert second_page == []


@pytest.mark.anyio
async def test_hidden_products_are_excluded_from_discovery_and_favorites(catalog):
    queries = [
        get_priority_products(catalog),
        get_products_for_category(catalog, 1),
        get_favourite_products_for_user(catalog, 1),
        get_candidate_products_for_categories(catalog, category_ids=[1], excluded_product_ids=set()),
        get_home_fallback_products(catalog, offset=0, limit=10, excluded_product_ids=set()),
    ]
    for query in queries:
        assert [product.id for product in await query] == [1]
    assert await get_similar_products(catalog, product_id=1) == []


@pytest.mark.anyio
async def test_hidden_product_detail_requires_explicit_internal_override(catalog):
    assert await get_product_by_id(catalog, 2) is None
    assert await get_product_by_id(catalog, 2, include_archived=True) is None
    assert (await get_product_by_id(catalog, 2, include_hidden=True)).id == 2


@pytest.mark.anyio
@pytest.mark.parametrize("scope", [None, (1,), ()])
async def test_hidden_product_access_is_denied_for_every_account_scope(catalog, scope):
    # This dependency runs before routes can return cached details or reviews.
    with pytest.raises(HTTPException) as error:
        await require_visible_product(2, scope=scope, db=catalog)
    assert error.value.status_code == 404
    if scope != ():
        await require_visible_product(1, scope=scope, db=catalog)


@pytest.mark.anyio
async def test_restored_product_reappears_without_losing_favorites(catalog):
    product = catalog.session.get(Product, 2)
    product.is_visible_in_app = True
    catalog.session.commit()
    await require_visible_product(2, scope=None, db=catalog)
    assert (await get_product_by_id(catalog, 2)).id == 2
    assert {product.id for product in await get_products(catalog)} == {1, 2}
    assert {product.id for product in await get_favourite_products_for_user(catalog, 1)} == {1, 2}


@pytest.mark.anyio
async def test_promotions_never_use_hidden_product_or_its_image(catalog):
    catalog.session.get(Product, 2).discount_percent = 20
    catalog.session.get(ProductCategory, 1).discount_percent = 10
    catalog.session.commit()
    request = Request({"type": "http", "headers": [], "scheme": "https", "server": ("test", 443)})
    promotions = await list_my_promotions(request, db=catalog, _current_user=None, scope=None)
    assert len(promotions) == 1
    assert promotions[0].kind == "category"
    assert promotions[0].product_id == 1


@pytest.mark.anyio
async def test_hidden_product_routes_reject_requests_before_reading_cached_content(catalog, monkeypatch):
    cache_factory = Mock()
    monkeypatch.setattr(products_router, "get_cache_service", cache_factory)
    app = FastAPI()
    app.include_router(products_router.products_router)
    app.dependency_overrides[get_db] = lambda: catalog
    app.dependency_overrides[get_catalog_scope] = lambda: None
    app.dependency_overrides[get_optional_current_user] = lambda: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for suffix in ("", "/similar", "/reviews", "/reviews/eligibility", "/questions"):
            response = await client.get(f"/products/2{suffix}")
            assert response.status_code == 404, (suffix, response.text)
    cache_factory.assert_not_called()
