import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

import src.app.services.basket as basket_service
import src.app.services.notifications.core as notifications_service
from src.app.services.ai.chat_interactive import _load_products, _load_variants
from src.app.services.ai.chat_tools import ShopAIToolExecutor
from src.app.services.ai.companion import dialogue_tools
from src.app.services.guest_checkout import _load_guest_variants, _validate_guest_variants
from src.app.services.orders.draft_items import _validate_checkout_items
from src.app.services.stock_visibility import StockVisibilityPolicy
from src.database import Base
from src.database.models import (
    Basket,
    BasketItem,
    Product,
    ProductByCategory,
    ProductCategory,
    StockNotificationSubscription,
    Variant,
)


class AsyncSessionAdapter:
    """Execute production queries against an isolated in-memory database."""

    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def commit(self):
        self.session.commit()


@pytest.fixture()
def catalog():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            Product.__table__,
            Variant.__table__,
            ProductCategory.__table__,
            ProductByCategory.__table__,
            StockNotificationSubscription.__table__,
        ],
    )
    with Session(engine) as session:
        visible = Product(id=1, sku="visible", name="Visible product", is_visible_in_app=True)
        hidden = Product(id=2, sku="hidden", name="Hidden product", is_visible_in_app=False)
        visible.variants = [Variant(id=11, sku="visible-variant", name="Visible variant", stock=20, price=Decimal("100.00"))]
        hidden.variants = [Variant(id=12, sku="hidden-variant", name="Hidden variant", stock=20, price=Decimal("100.00"))]
        session.add_all([visible, hidden])
        session.commit()
        yield AsyncSessionAdapter(session), visible, hidden
    engine.dispose()


@pytest.mark.parametrize("enabled", [True, False])
def test_hiding_product_blocks_available_stock_without_changing_inventory(enabled):
    product = SimpleNamespace(is_visible_in_app=False, stock_reduction_override=0)
    policy = StockVisibilityPolicy(enabled=enabled, global_reduction=5)
    assert policy.visible_stock(20, product) == 0
    product.is_visible_in_app = True
    assert policy.visible_stock(20, product) == 20


def test_hidden_products_are_absent_from_ai_search_detail_stock_and_cards(catalog):
    db, visible, hidden = catalog

    async def run():
        executor = ShopAIToolExecutor(db, user_id=1)
        search = await executor.search_catalog_products(query="", limit=20, offset=0)
        assert [item["product_id"] for item in search["items"]] == [visible.id]
        assert await executor.get_catalog_product(product_id=hidden.id) == {"ok": False, "error": "product_not_found"}
        assert await executor.get_product_stock(product_id=hidden.id) == {"ok": False, "error": "product_not_found"}
        assert await executor.get_product_stock(variant_id=12) == {"ok": False, "error": "variant_not_found"}
        assert set(await _load_products(db, {visible.id, hidden.id})) == {visible.id}
        assert set(await _load_variants(db, {11, 12})) == {11}

    asyncio.run(run())


def test_hidden_products_cannot_be_quoted_for_guest_checkout(catalog, monkeypatch):
    db, _, hidden = catalog
    monkeypatch.setattr("src.app.services.guest_checkout.customer_category_scope", lambda _: None)

    async def run():
        variants = await _load_guest_variants(db, {11: 1, 12: 1})
        assert set(variants) == {11}
        with pytest.raises(HTTPException) as error:
            _validate_guest_variants({11: 1, 12: 1}, variants, StockVisibilityPolicy())
        assert error.value.status_code == 404

    asyncio.run(run())
    assert hidden.variants[0].stock == 20


def test_existing_hidden_basket_items_cannot_be_checked_out(catalog):
    _, _, hidden = catalog
    variant = hidden.variants[0]
    item = SimpleNamespace(variant_id=variant.id, quantity=1)
    policy = StockVisibilityPolicy()
    with pytest.raises(HTTPException) as error:
        _validate_checkout_items([item], {variant.id: variant}, policy)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as guest_error:
        _validate_guest_variants({variant.id: 1}, {variant.id: variant}, policy)
    assert guest_error.value.status_code == 409
    assert variant.stock == 20


def test_existing_basket_shows_hidden_product_as_unavailable(catalog):
    db, _, hidden = catalog
    variant = hidden.variants[0]
    now = datetime.now(timezone.utc)
    basket = Basket(
        id=1,
        user_id=1,
        delivery_total=Decimal("0.00"),
        currency="RUB",
        created_at=now,
        updated_at=now,
    )
    basket.items = [BasketItem(
        id=1,
        user_id=1,
        product=hidden,
        variant=variant,
        variant_id=variant.id,
        quantity=1,
        price=variant.price,
        created_at=now,
        updated_at=now,
    )]
    request = Request({
        "type": "http",
        "scheme": "https",
        "server": ("example.test", 443),
        "path": "/",
        "headers": [],
        "query_string": b"",
    })
    with db.session.no_autoflush:
        result = basket_service.serialize_basket(request, basket)
    assert result.has_unavailable_items is True
    assert result.items[0].is_available is False
    assert result.items[0].available_quantity == 0
    assert variant.stock == 20


def test_adding_hidden_product_to_basket_is_rejected(catalog, monkeypatch):
    _, _, hidden = catalog
    monkeypatch.setattr(basket_service, "_get_or_create_locked_basket", AsyncMock(return_value=SimpleNamespace(id=1)))
    monkeypatch.setattr(basket_service, "_get_variant_for_update", AsyncMock(return_value=hidden.variants[0]))
    monkeypatch.setattr(basket_service, "_get_product_for_pricing", AsyncMock(return_value=hidden))
    with pytest.raises(HTTPException) as error:
        asyncio.run(basket_service.add_variant_to_basket_for_user(None, user_id=1, variant_id=12))
    assert error.value.status_code == 404


def test_companion_matching_does_not_suggest_hidden_products(catalog, monkeypatch):
    db, _, _ = catalog
    monkeypatch.setattr(dialogue_tools.service, "profile_for", AsyncMock(return_value=SimpleNamespace(enabled=True)))
    result = asyncio.run(dialogue_tools.execute_dialogue_tool(db, 1, "match_course_products", {"query": "product"}, True))
    assert [item["variant_id"] for item in result["data"]["candidates"]] == [11]


def test_restock_notifications_skip_hidden_products_and_resume_when_visible(catalog, monkeypatch):
    db, _, hidden = catalog
    subscription = StockNotificationSubscription(id=1, user_id=1, variant_id=12, is_active=True, last_seen_stock=0)
    db.session.add(subscription)
    db.session.commit()
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(notifications_service, "_send_and_record", send)

    assert asyncio.run(notifications_service.process_restock_notifications(db)) == 0
    send.assert_not_awaited()
    assert subscription.is_active is True

    hidden.is_visible_in_app = True
    db.session.commit()
    assert asyncio.run(notifications_service.process_restock_notifications(db)) == 1
    send.assert_awaited_once()
    assert subscription.is_active is False
