import sys
import types
import uuid

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if "PIL" not in sys.modules:
    pil_module = types.ModuleType("PIL")
    pil_module.Image = types.SimpleNamespace(open=None)

    class _UnidentifiedImageError(Exception):
        pass

    pil_module.UnidentifiedImageError = _UnidentifiedImageError
    sys.modules["PIL"] = pil_module

from config import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER
from src.app.main import app
from src.database.models import Product, ProductByCategory, ProductCategory, Variant

SYNC_DB_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
sync_engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)


def _create_category(session: Session, *, name: str) -> ProductCategory:
    category = ProductCategory(name=name, description=None)
    session.add(category)
    session.flush()
    return category


def _create_product(
    session: Session,
    *,
    name: str,
    sku: str,
    category_id: int,
    description: str | None,
    usage: str | None,
    stock: int,
    price: Decimal,
    priority: int,
) -> Product:
    product = Product(
        name=name,
        sku=sku,
        description=description,
        usage=usage,
        expiration=None,
        in_stock=stock > 0,
        priority=priority,
    )
    session.add(product)
    session.flush()

    session.add(ProductByCategory(product_id=product.id, category_id=category_id))
    session.flush()

    session.add(
        Variant(
            product_id=product.id,
            sku=f"{sku}-v",
            name=f"{name} variant",
            stock=stock,
            price=price,
        )
    )
    session.flush()
    return product


def _seed_search_products() -> dict[str, int]:
    token = uuid.uuid4().hex[:8]
    created_product_ids: list[int] = []
    created_category_ids: list[int] = []
    with Session(sync_engine) as session:
        category_peptides = _create_category(session, name=f"Пептиды-{token}")
        category_accessories = _create_category(session, name=f"Аксессуары-{token}")
        created_category_ids.extend([int(category_peptides.id), int(category_accessories.id)])

        product_ru = _create_product(
            session,
            name=f"Рета Пептид {token}",
            sku=f"RET-RU-{token}",
            category_id=category_peptides.id,
            description="Супер средство для восстановления",
            usage="Курс применения рета",
            stock=10,
            price=Decimal("30.00"),
            priority=10,
        )
        product_en = _create_product(
            session,
            name=f"Reta Mix {token}",
            sku=f"RET-EN-{token}",
            category_id=category_accessories.id,
            description="Accessory pack for reta program",
            usage="Mix usage",
            stock=10,
            price=Decimal("20.00"),
            priority=4,
        )
        product_noise = _create_product(
            session,
            name=f"Omega Support {token}",
            sku=f"OMG-{token}",
            category_id=category_accessories.id,
            description="Completely different product",
            usage="Daily usage",
            stock=10,
            price=Decimal("10.00"),
            priority=1,
        )
        created_product_ids.extend([int(product_ru.id), int(product_en.id), int(product_noise.id)])
        session.commit()

    return {
        "ru_product_id": created_product_ids[0],
        "en_product_id": created_product_ids[1],
        "noise_product_id": created_product_ids[2],
        "peptides_category_id": created_category_ids[0],
        "accessories_category_id": created_category_ids[1],
        "peptides_category_name": f"Пептиды-{token}",
        "ru_product_sku": f"RET-RU-{token}",
        "en_product_sku": f"RET-EN-{token}",
    }


def _cleanup_seed(data: dict[str, int]) -> None:
    with Session(sync_engine) as session:
        for product_id in [data["ru_product_id"], data["en_product_id"], data["noise_product_id"]]:
            product = session.get(Product, product_id)
            if product is not None:
                session.delete(product)
        for category_id in [data["peptides_category_id"], data["accessories_category_id"]]:
            category = session.get(ProductCategory, category_id)
            if category is not None:
                session.delete(category)
        session.commit()


def _response_product_ids(response) -> list[int]:
    payload = response.json()
    return [int(item["id"]) for item in payload]


def test_products_advanced_search_variants_and_regressions():
    seed = _seed_search_products()
    try:
        with TestClient(app) as client:
            exact = client.get("/api/v1/products", params={"q": "Рета"})
            assert exact.status_code == 200, exact.text
            assert seed["ru_product_id"] in _response_product_ids(exact)

            partial = client.get("/api/v1/products", params={"q": "восстановления"})
            assert partial.status_code == 200, partial.text
            assert seed["ru_product_id"] in _response_product_ids(partial)

            category_name = client.get("/api/v1/products", params={"q": seed["peptides_category_name"]})
            assert category_name.status_code == 200, category_name.text
            assert seed["ru_product_id"] in _response_product_ids(category_name)

            translit = client.get("/api/v1/products", params={"q": "reta"})
            assert translit.status_code == 200, translit.text
            translit_ids = _response_product_ids(translit)
            assert seed["ru_product_id"] in translit_ids
            assert seed["en_product_id"] in translit_ids

            wrong_layout_en_to_ru = client.get("/api/v1/products", params={"q": "htnf"})
            assert wrong_layout_en_to_ru.status_code == 200, wrong_layout_en_to_ru.text
            assert seed["ru_product_id"] in _response_product_ids(wrong_layout_en_to_ru)

            wrong_layout_ru_to_en = client.get("/api/v1/products", params={"q": "куеф"})
            assert wrong_layout_ru_to_en.status_code == 200, wrong_layout_ru_to_en.text
            assert seed["en_product_id"] in _response_product_ids(wrong_layout_ru_to_en)

            mixed_case = client.get("/api/v1/products", params={"q": "   рЕтА   "})
            assert mixed_case.status_code == 200, mixed_case.text
            assert seed["ru_product_id"] in _response_product_ids(mixed_case)

            fuzzy = client.get("/api/v1/products", params={"q": "retaa"})
            assert fuzzy.status_code == 200, fuzzy.text
            assert seed["en_product_id"] in _response_product_ids(fuzzy)

            # SKU search should work for punctuated and compact input alike.
            sku_punctuated = client.get("/api/v1/products", params={"q": seed["ru_product_sku"]})
            assert sku_punctuated.status_code == 200, sku_punctuated.text
            assert seed["ru_product_id"] in _response_product_ids(sku_punctuated)

            compact_sku_query = seed["ru_product_sku"].replace("-", "")
            sku_compact = client.get("/api/v1/products", params={"q": compact_sku_query})
            assert sku_compact.status_code == 200, sku_compact.text
            assert seed["ru_product_id"] in _response_product_ids(sku_compact)

            # Category filtering still applies.
            filtered = client.get(
                "/api/v1/products",
                params={"q": "reta", "category_id": seed["peptides_category_id"]},
            )
            assert filtered.status_code == 200, filtered.text
            filtered_ids = _response_product_ids(filtered)
            assert seed["ru_product_id"] in filtered_ids
            assert seed["en_product_id"] not in filtered_ids

            # Pagination and sorting still behave with search.
            page_1 = client.get(
                "/api/v1/products",
                params={"q": "reta", "sort": "name_asc", "limit": 1, "offset": 0},
            )
            page_2 = client.get(
                "/api/v1/products",
                params={"q": "reta", "sort": "name_asc", "limit": 1, "offset": 1},
            )
            assert page_1.status_code == 200, page_1.text
            assert page_2.status_code == 200, page_2.text
            page_1_ids = _response_product_ids(page_1)
            page_2_ids = _response_product_ids(page_2)
            assert len(page_1_ids) == 1
            assert len(page_2_ids) == 1
            assert page_1_ids[0] != page_2_ids[0]
    finally:
        _cleanup_seed(seed)
