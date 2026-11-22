import asyncio
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from src.app.modules.products.helpers import variant_image_url
from src.app.services.basket import _variant_image_url
from src.database.crud.catalog.product import get_products
from src.database.models import Product, ProductByCategory, ProductCategory, Variant
from test_orders_api import sync_engine, variant_factory


class AsyncQueryAdapter:
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


def test_price_sort_matches_discounted_tile_and_ignores_archived_and_unavailable_variants(variant_factory):
    first = variant_factory(price=Decimal("100"))
    second = variant_factory(price=Decimal("75"))
    third = variant_factory(price=Decimal("190"))
    token = uuid4().hex
    with Session(sync_engine) as db:
        for item in [first, second, third]:
            p = db.get(Product, item["product_id"])
            p.name = f"sort-{token}-{p.id}"
            p.in_stock = True
        db.get(Product, first["product_id"]).discount_percent = Decimal("50")
        db.add_all([
            Variant(product_id=first["product_id"], name="Large", stock=5, price=Decimal("10000")),
            Variant(product_id=third["product_id"], name="Archived", archived=True, stock=5, price=Decimal("0")),
            Variant(product_id=third["product_id"], name="Unavailable", stock=0, price=Decimal("1")),
        ])
        db.commit()
        for sort, expected in [
            ("price_asc", [first, second, third]),
            ("price_desc", [third, second, first]),
        ]:
            products = asyncio.run(get_products(AsyncQueryAdapter(db), q=token, sort=sort))
            assert [p.id for p in products] == [x["product_id"] for x in expected]


def test_sort_respects_category_discount_and_personal_discount_exclusions(variant_factory):
    eligible = variant_factory(price=Decimal("100"))
    excluded = variant_factory(price=Decimal("90"))
    token = uuid4().hex
    category_ids = []
    try:
        with Session(sync_engine) as db:
            for item in [eligible, excluded]:
                p = db.get(Product, item["product_id"])
                p.name = f"sort-{token}-{p.id}"
                p.in_stock = True
            category = ProductCategory(name=f"sort-{token}", discount_percent=Decimal("10"))
            db.add(category)
            db.flush()
            category_ids.append(category.id)
            db.add(ProductByCategory(product_id=eligible["product_id"], category_id=category.id))
            existing = db.query(ProductCategory).filter(ProductCategory.name == "Сопутствующие товары").one_or_none()
            if existing is None:
                existing = ProductCategory(name="Сопутствующие товары")
                db.add(existing)
                db.flush()
                category_ids.append(existing.id)
            db.add(ProductByCategory(product_id=excluded["product_id"], category_id=existing.id))
            db.commit()
            products = asyncio.run(get_products(AsyncQueryAdapter(db), q=token, sort="price_asc", personal_discount_percent=Decimal("20")))
            assert [p.id for p in products] == [eligible["product_id"], excluded["product_id"]]
    finally:
        with Session(sync_engine) as db:
            for category_id in category_ids:
                db.delete(db.get(ProductCategory, category_id))
            db.commit()


def test_price_sort_uses_visible_stock_after_stock_reduction(variant_factory):
    first = variant_factory(price=Decimal("1"), stock=1)
    second = variant_factory(price=Decimal("75"), stock=10)
    token = uuid4().hex
    with Session(sync_engine) as db:
        for item in [first, second]:
            p = db.get(Product, item["product_id"])
            p.name = f"sort-{token}-{p.id}"
            p.in_stock = True
        db.add(Variant(product_id=first["product_id"], name="Available", stock=10, price=Decimal("100")))
        db.commit()
        products = asyncio.run(get_products(AsyncQueryAdapter(db), q=token, sort="price_asc", stock_reduction_enabled=True, stock_reduction=2))
        assert [p.id for p in products] == [second["product_id"], first["product_id"]]


@pytest.mark.parametrize("build_url", [variant_image_url, _variant_image_url])
def test_missing_variant_image_uses_product_photo_before_placeholder(tmp_path, build_url):
    product_photo = tmp_path / "product-photo.png"
    product_photo.write_bytes(b"photo")
    variant_photo = tmp_path / "variant-photo.png"
    variant_photo.write_bytes(b"photo")
    request = SimpleNamespace(base_url="https://example.test")
    product = SimpleNamespace(image_path=product_photo)
    fallback = build_url(request, SimpleNamespace(image_path=None), product=product)
    assert "product-photo.png" in fallback
    own = build_url(request, SimpleNamespace(image_path=variant_photo), product=product)
    assert "variant-photo.png" in own
    placeholder = build_url(request, SimpleNamespace(image_path=None), product=SimpleNamespace(image_path=None))
    assert placeholder.endswith("/media/products/product.png")
