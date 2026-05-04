from decimal import Decimal
from uuid import UUID

from src.database.models import Product, Variant
from src.integrations.moysklad.client import MoySkladClient
from src.integrations.moysklad.schemas import MoySkladCatalogSyncStats, MoySkladInitialRelinkStats


OLD_PRODUCT_ID = UUID("b019df8a-5a25-11f0-9098-fa163e347889")
NEW_PRODUCT_ID = UUID("3d5c6d1c-9b81-11f0-9184-fa163eccf8af")
VARIANT_5_ID = UUID("11111111-1111-1111-1111-111111111111")
VARIANT_10_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_moysklad_variant_rows_use_product_meta_id_and_stock_assortment_id():
    client = MoySkladClient(token="token", base_url="https://example.test", stock_reserve=3)
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

    product_rows, products_by_external_code, products_by_id = client._build_product_rows(products, stats)
    variant_rows = client._build_variant_rows(
        variants=variants,
        stocks=stocks,
        products_by_external_code=products_by_external_code,
        products_by_id=products_by_id,
        stats=stats,
    )

    assert product_rows[0].system_id == NEW_PRODUCT_ID
    assert variant_rows[0].system_id == VARIANT_5_ID
    assert variant_rows[0].product_system_id == NEW_PRODUCT_ID
    assert variant_rows[0].price == Decimal("150.5")
    assert variant_rows[0].stock == 5


def test_moysklad_variant_rows_strip_parent_product_name():
    client = MoySkladClient(token="token", base_url="https://example.test")
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

    _, products_by_external_code, products_by_id = client._build_product_rows(products, stats)
    variant_rows = client._build_variant_rows(
        variants=variants,
        stocks=[],
        products_by_external_code=products_by_external_code,
        products_by_id=products_by_id,
        stats=stats,
    )

    assert [row.name for row in variant_rows] == ["5 mg", "Standalone 10 mg"]


def test_moysklad_product_rows_skip_package_product():
    stats = MoySkladCatalogSyncStats()
    product_rows, products_by_external_code, products_by_id = MoySkladClient._build_product_rows(
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
    product_rows, _, _ = MoySkladClient._build_product_rows(
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


def test_initial_relink_variant_matching_uses_characteristics_and_skips_ambiguous():
    client = MoySkladClient(token="token", base_url="https://example.test")
    product = Product(id=1, system_id=OLD_PRODUCT_ID, sku="P-001", name="Peptide", description=None, usage=None, expiration=None)
    local_5 = Variant(id=10, product_id=1, system_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"), sku=None, name="5 mg", stock=0, price=Decimal("0"))
    local_10 = Variant(id=11, product_id=1, system_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"), sku=None, name="10 mg", stock=0, price=Decimal("0"))
    stats = MoySkladInitialRelinkStats()

    matches = client._match_variants_for_product(
        local_product=product,
        local_variants=[local_5, local_10],
        moy_variants=[
            {"id": str(VARIANT_5_ID), "name": "Peptide 5 mg", "characteristics": [{"name": "Dose", "value": "5 mg"}]},
            {"id": str(VARIANT_10_ID), "name": "Peptide 10 mg", "characteristics": [{"name": "Dose", "value": "10 mg"}]},
        ],
        variants_by_system_id={local_5.system_id: local_5, local_10.system_id: local_10},
        stats=stats,
    )

    assert [(local.id, new_id) for local, _, new_id, _ in matches] == [(10, VARIANT_5_ID), (11, VARIANT_10_ID)]
    assert stats.skipped_variants_missing_local == 0

    ambiguous_stats = MoySkladInitialRelinkStats()
    ambiguous_matches = client._match_variants_for_product(
        local_product=product,
        local_variants=[local_5, Variant(id=12, product_id=1, system_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"), sku=None, name="5 mg", stock=0, price=Decimal("0"))],
        moy_variants=[{"id": str(VARIANT_5_ID), "name": "Peptide 5 mg", "characteristics": [{"name": "Dose", "value": "5 mg"}]}],
        variants_by_system_id={},
        stats=ambiguous_stats,
    )

    assert ambiguous_matches == []
    assert ambiguous_stats.skipped_variants_ambiguous >= 1
