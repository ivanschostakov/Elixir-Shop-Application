from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from config import ufa_now
from src.app.modules.products.helpers import ProductPriceDiscountContext, resolve_variant_price
from src.app.services.catalog_merchandising import (
    CatalogMerchandisingPolicy,
    apply_percent_discount,
    product_catalog_discount_percent,
    product_is_new,
)
from src.database.models import Product
from src.database.crud.catalog.product import get_products


def _category_link(percent: str, *, archived: bool = False):
    return SimpleNamespace(
        category=SimpleNamespace(
            archived=archived,
            discount_percent=Decimal(percent),
            name="Категория",
        )
    )


def _product(
    *,
    created_days_ago: int = 0,
    manual_new: bool = False,
    discount_percent: str = "0",
    category_discounts: tuple[str, ...] = (),
):
    return SimpleNamespace(
        created_at=ufa_now() - timedelta(days=created_days_ago),
        is_new_manual=manual_new,
        discount_percent=Decimal(discount_percent),
        products_by_category=[_category_link(value) for value in category_discounts],
    )


def test_new_product_window_and_manual_override():
    policy = CatalogMerchandisingPolicy(new_product_days=14)

    assert product_is_new(_product(created_days_ago=13), policy)
    assert not product_is_new(_product(created_days_ago=15), policy)
    assert product_is_new(_product(created_days_ago=365, manual_new=True), policy)
    assert not product_is_new(_product(), CatalogMerchandisingPolicy(new_product_days=0))


def test_best_product_or_category_discount_wins():
    product = _product(
        discount_percent="12.50",
        category_discounts=("10.00", "25.00"),
    )
    product.products_by_category.append(_category_link("80.00", archived=True))

    assert product_catalog_discount_percent(product) == Decimal("25.00")


def test_catalog_discount_is_applied_before_personal_discount():
    product = Product(
        sku="discount-test",
        name="Discount test",
        discount_percent=Decimal("20.00"),
    )
    product.products_by_category = []
    original, discounted, effective, catalog, personal = resolve_variant_price(
        Decimal("100.00"),
        ProductPriceDiscountContext(app_referral_percent=Decimal("10.00")),
        product=product,
    )

    assert original == Decimal("100.00")
    assert discounted == Decimal("72.00")
    assert effective == Decimal("28.00")
    assert catalog == Decimal("20.00")
    assert personal == Decimal("10.00")


def test_discount_rounding_is_money_safe():
    assert apply_percent_discount(Decimal("99.99"), Decimal("15.00")) == Decimal("84.99")


@pytest.mark.anyio
async def test_new_only_filter_and_search_ranking_are_part_of_catalog_query():
    class EmptyResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class CapturingSession:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return EmptyResult()

    session = CapturingSession()
    await get_products(
        session,
        q="новинка",
        new_only=True,
        new_product_days=21,
        sort="newest",
    )

    sql = str(
        session.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "products.is_new_manual IS true" in sql
    assert "products.created_at >=" in sql
    assert "ORDER BY products.in_stock DESC" in sql
