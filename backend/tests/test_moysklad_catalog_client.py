from decimal import Decimal
from uuid import UUID

import pytest

from src.database.models import Product, Variant
from src.integrations.moysklad.rows import build_product_rows, build_variant_rows
from src.integrations.moysklad.schemas import (
    MoySkladCatalogSyncStats,
    MoySkladProductRow,
    MoySkladVariantRow,
)
from src.integrations.moysklad.sync import upsert_catalog_rows


OLD_PRODUCT_ID = UUID("b019df8a-5a25-11f0-9098-fa163e347889")
NEW_PRODUCT_ID = UUID("3d5c6d1c-9b81-11f0-9184-fa163eccf8af")
VARIANT_5_ID = UUID("11111111-1111-1111-1111-111111111111")
VARIANT_10_ID = UUID("22222222-2222-2222-2222-222222222222")


class _FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _FakeSession:
    def __init__(self, *, products, variants):
        self._results = [products, variants]
        self.added = []
        self.flushes = 0

    async def execute(self, *_args, **_kwargs):
        return _FakeScalarResult(self._results.pop(0))

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushes += 1


def test_moysklad_variant_rows_use_product_meta_id_and_stock_assortment_id():
    stats = MoySkladCatalogSyncStats()
    products = [
        {
            "id": str(NEW_PRODUCT_ID),
            "externalCode": str(OLD_PRODUCT_ID),
            "article": "P-001",
            "name": "Product",
        }
    ]
    variants = [
        {
            "id": str(VARIANT_5_ID),
            "externalCode": str(OLD_PRODUCT_ID),
            "code": "V-001",
            "name": "5 mg",
            "product": {"id": str(NEW_PRODUCT_ID), "externalCode": str(OLD_PRODUCT_ID)},
            "salePrices": [{"value": 15050}],
        }
    ]
    stocks = [{"assortmentId": str(VARIANT_5_ID), "quantity": 8}]

    product_rows, products_by_external_code, products_by_id = build_product_rows(products, stats)
    variant_rows = build_variant_rows(
        variants,
        stocks,
        products_by_external_code,
        products_by_id,
        stats,
        reserve=3,
    )

    assert product_rows[0].system_id == NEW_PRODUCT_ID
    assert variant_rows[0].system_id == VARIANT_5_ID
    assert variant_rows[0].product_system_id == NEW_PRODUCT_ID
    assert variant_rows[0].price == Decimal("150.5")
    assert variant_rows[0].stock == 5


def test_moysklad_variant_rows_strip_parent_product_name():
    stats = MoySkladCatalogSyncStats()
    products = [
        {
            "id": str(NEW_PRODUCT_ID),
            "externalCode": str(OLD_PRODUCT_ID),
            "article": "P-001",
            "name": "Product",
        }
    ]
    variants = [
        {
            "id": str(VARIANT_5_ID),
            "externalCode": str(OLD_PRODUCT_ID),
            "code": "V-001",
            "name": "Product (5 mg)",
            "product": {"id": str(NEW_PRODUCT_ID), "externalCode": str(OLD_PRODUCT_ID)},
        },
        {
            "id": str(VARIANT_10_ID),
            "externalCode": str(OLD_PRODUCT_ID),
            "code": "V-002",
            "name": "Standalone 10 mg",
            "product": {"id": str(NEW_PRODUCT_ID), "externalCode": str(OLD_PRODUCT_ID)},
        },
    ]

    _, products_by_external_code, products_by_id = build_product_rows(products, stats)
    variant_rows = build_variant_rows(
        variants,
        [],
        products_by_external_code,
        products_by_id,
        stats,
    )

    assert [row.name for row in variant_rows] == ["5 mg", "Standalone 10 mg"]


def test_moysklad_product_rows_skip_package_product():
    stats = MoySkladCatalogSyncStats()
    product_rows, products_by_external_code, products_by_id = build_product_rows(
        [
            {
                "id": str(NEW_PRODUCT_ID),
                "externalCode": str(OLD_PRODUCT_ID),
                "code": "PKG",
                "name": "ПАКЕТ фирменный, малый",
            }
        ],
        stats,
    )

    assert product_rows == []
    assert products_by_external_code == {}
    assert products_by_id == {}
    assert stats.skipped_products_excluded_name == 1


def test_moysklad_product_row_unarchives_fetched_products():
    stats = MoySkladCatalogSyncStats()
    product_rows, _, _ = build_product_rows(
        [
            {
                "id": str(NEW_PRODUCT_ID),
                "externalCode": str(OLD_PRODUCT_ID),
                "code": "P-001",
                "name": "Product",
                "archived": True,
            }
        ],
        stats,
    )

    assert product_rows[0].archived is False


@pytest.mark.anyio
async def test_moysklad_upsert_keeps_existing_archived_rows_archived():
    product = Product(
        id=1,
        system_id=NEW_PRODUCT_ID,
        sku="P-001",
        name="Product",
        description=None,
        usage=None,
        expiration=None,
        archived=True,
        in_stock=True,
    )
    variant = Variant(
        id=10,
        system_id=VARIANT_5_ID,
        product_id=1,
        sku="V-001",
        name="5 mg",
        stock=0,
        archived=True,
        price=Decimal("10"),
    )
    session = _FakeSession(products=[product], variants=[variant])

    stats = await upsert_catalog_rows(
        session,
        products=[
            MoySkladProductRow(
                system_id=NEW_PRODUCT_ID,
                sku="P-001",
                name="Product",
                description=None,
                archived=False,
            )
        ],
        variants=[
            MoySkladVariantRow(
                system_id=VARIANT_5_ID,
                product_system_id=NEW_PRODUCT_ID,
                sku="V-001",
                name="5 mg",
                stock=8,
                price=Decimal("10"),
            )
        ],
    )

    assert product.archived is True
    assert product.in_stock is False
    assert variant.archived is True
    assert variant.stock == 8
    assert stats.unarchived_products == 0
    assert stats.unarchived_variants == 0
