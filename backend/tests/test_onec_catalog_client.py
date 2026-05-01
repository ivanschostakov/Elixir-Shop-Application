from decimal import Decimal
from uuid import UUID

from src.integrations.onec.client import OneCCatalogClient, OneCCatalogSyncStats


PRODUCT_ID = UUID("b019df8a-5a25-11f0-9098-fa163e347889")
FEATURE_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_onec_product_and_feature_ids_map_to_system_ids():
    client = OneCCatalogClient(base_url="https://onec.example/odata", username="user", password="pass", stock_reserve=3)
    stats = OneCCatalogSyncStats()
    products = {
        str(PRODUCT_ID): {
            "onec_id": str(PRODUCT_ID),
            "sku": "P-001",
            "name": "Product",
            "description": "Description\r\n  line",
            "usage": "Usage   text",
            "expiration": "Expiration\r\nvalue",
        }
    }
    features = {
        str(FEATURE_ID): {
            "onec_id": str(FEATURE_ID),
            "product_onec_id": str(PRODUCT_ID),
            "name": "10 mg",
            "sku": "V-001",
        }
    }

    product_rows = client._build_product_rows(products, stats)
    feature_rows = client._merge_feature_rows(
        products,
        features,
        {f"{PRODUCT_ID}_{FEATURE_ID}": {"price": "150.50"}},
        {f"{PRODUCT_ID}_{FEATURE_ID}": {"balance": "8"}},
        stats,
    )
    variant_rows = client._build_variant_rows(feature_rows, stats)

    assert product_rows[0].system_id == PRODUCT_ID
    assert product_rows[0].description == "Description line"
    assert product_rows[0].usage == "Usage text"
    assert product_rows[0].expiration == "Expiration value"
    assert variant_rows[0].system_id == FEATURE_ID
    assert variant_rows[0].product_system_id == PRODUCT_ID
    assert variant_rows[0].price == Decimal("150.50")
    assert variant_rows[0].stock == 5


def test_synthetic_variant_uses_stable_uuid_system_id_for_empty_onec_feature():
    client = OneCCatalogClient(base_url="https://onec.example/odata", username="user", password="pass", stock_reserve=3)
    stats = OneCCatalogSyncStats()
    products = {str(PRODUCT_ID): {"onec_id": str(PRODUCT_ID), "sku": "P-001", "name": "Product"}}

    feature_rows = client._merge_feature_rows(
        products,
        {},
        {f"{PRODUCT_ID}_{client.EMPTY_FEATURE_KEY}": {"price": "99"}},
        {f"{PRODUCT_ID}_{client.EMPTY_FEATURE_KEY}": {"balance": "4"}},
        stats,
    )
    variant_rows = client._build_variant_rows(feature_rows, stats)

    assert stats.synthetic_variants == 1
    assert variant_rows[0].system_id == client.synthetic_variant_system_id(PRODUCT_ID)
    assert variant_rows[0].product_system_id == PRODUCT_ID
    assert variant_rows[0].sku == "__AUTO_DEFAULT__"
    assert variant_rows[0].name == "Основной вариант"
    assert variant_rows[0].stock == 1


def test_parse_odata_feed_extracts_extra_requisites():
    xml = """
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
          xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
      <entry>
        <content>
          <m:properties>
            <d:Ref_Key>b019df8a-5a25-11f0-9098-fa163e347889</d:Ref_Key>
            <d:Description>Product</d:Description>
            <d:ДополнительныеРеквизиты>
              <d:element>
                <d:Свойство_Key>87cfc3b4-defa-11f0-8b75-fa163eccf8af</d:Свойство_Key>
                <d:Значение>false</d:Значение>
              </d:element>
            </d:ДополнительныеРеквизиты>
          </m:properties>
        </content>
      </entry>
    </feed>
    """.encode()

    rows = OneCCatalogClient.parse_odata_feed(xml)

    assert rows == [
        {
            "Ref_Key": "b019df8a-5a25-11f0-9098-fa163e347889",
            "Description": "Product",
            "ДополнительныеРеквизиты": [
                {
                    "Свойство_Key": "87cfc3b4-defa-11f0-8b75-fa163eccf8af",
                    "Значение": "false",
                }
            ],
        }
    ]
