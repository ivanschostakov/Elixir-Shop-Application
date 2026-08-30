from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from starlette.requests import Request

from src.app.modules.products.helpers import serialize_product_with_variants
from src.app.services.stock_visibility import StockVisibilityPolicy
from src.database.models import Product, Variant


def test_global_stock_reduction_is_applied_and_clamped_to_zero():
    policy = StockVisibilityPolicy(enabled=True, global_reduction=5)
    product = SimpleNamespace(stock_reduction_override=None)

    assert policy.visible_stock(12, product) == 7
    assert policy.visible_stock(3, product) == 0


def test_product_stock_reduction_overrides_global_setting():
    policy = StockVisibilityPolicy(enabled=True, global_reduction=5)

    assert policy.visible_stock(
        12,
        SimpleNamespace(stock_reduction_override=2),
    ) == 10
    assert policy.visible_stock(
        12,
        SimpleNamespace(stock_reduction_override=0),
    ) == 12


def test_disabled_global_setting_keeps_actual_stock():
    policy = StockVisibilityPolicy(enabled=False, global_reduction=5)

    assert policy.visible_stock(
        12,
        SimpleNamespace(stock_reduction_override=None),
    ) == 12
    assert policy.visible_stock(
        12,
        SimpleNamespace(stock_reduction_override=3),
    ) == 12


def test_public_product_payload_exposes_reduced_stock_only():
    now = datetime.now(timezone.utc)
    product = Product(
        id=1,
        system_id=uuid4(),
        sku="P-1",
        name="Product",
        in_stock=True,
        archived=False,
        priority=0,
        is_new_manual=False,
        discount_percent=Decimal("0.00"),
        stock_reduction_override=None,
        created_at=now,
        updated_at=now,
    )
    variant = Variant(
        id=10,
        system_id=uuid4(),
        product_id=product.id,
        sku="V-1",
        name="Variant",
        stock=4,
        archived=False,
        price=Decimal("100.00"),
        created_at=now,
        updated_at=now,
    )
    product.variants = [variant]
    request = Request(
        {
            "type": "http",
            "scheme": "https",
            "server": ("example.test", 443),
            "root_path": "",
            "path": "/api/v1/products/1",
            "query_string": b"",
            "headers": [],
        }
    )

    payload = serialize_product_with_variants(
        request,
        product,
        stock_policy=StockVisibilityPolicy(enabled=True, global_reduction=5),
    )

    assert payload.variants[0].stock == 0
    assert payload.in_stock is False
    assert variant.stock == 4
