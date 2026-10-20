import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import src.app.modules.admin.catalog as admin_catalog
import src.app.services.admin.permissions as admin_permissions
from src.app.services.admin.permissions import AdminContext, get_current_admin_context
from src.database import get_db
from src.database.models import (
    CatalogSettings,
    Product,
    ProductByCategory,
    ProductCategory,
    Variant,
)
from src.integrations.moysklad.schemas import MoySkladProductRow, MoySkladVariantRow
from src.integrations.moysklad.sync import upsert_catalog_rows


class AsyncSessionAdapter:
    """Use the real ORM with isolated SQLite storage for endpoint tests."""

    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def get(self, model, identity):
        return self.session.get(model, identity)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()


@pytest.fixture()
def visibility_api(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (Product, ProductCategory, ProductByCategory, Variant, CatalogSettings):
        model.__table__.create(engine)
    with Session(engine) as session:
        session.add(Product(id=1, sku="VISIBILITY-1", name="Visibility product", in_stock=True))
        session.add(Variant(id=10, product_id=1, name="Standard", stock=8, price=100))
        session.commit()

    async def database():
        with Session(engine, expire_on_commit=False) as session:
            yield AsyncSessionAdapter(session)

    permissions = {"catalog.read", "catalog.merchandise"}

    def context():
        return AdminContext(
            user=SimpleNamespace(id=42),
            admin=SimpleNamespace(user_id=42),
            session=SimpleNamespace(id=7),
            roles=("content",),
            permissions=frozenset(permissions),
        )

    audit = AsyncMock()
    cache = SimpleNamespace(bump_namespace=AsyncMock())
    monkeypatch.setattr(admin_catalog, "add_admin_audit", audit)
    monkeypatch.setattr(admin_catalog, "get_cache_service", lambda: cache)
    monkeypatch.setattr(admin_permissions, "ADMIN_READ_ONLY", False)
    app = FastAPI()
    app.include_router(admin_catalog.admin_catalog_router, prefix="/admin")
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_admin_context] = context
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client, engine=engine, permissions=permissions, audit=audit, cache=cache
        )
    engine.dispose()


def test_admin_can_hide_and_restore_product_without_losing_catalog_data(visibility_api):
    api = visibility_api
    initial = api.client.get("/admin/products/1")
    assert initial.status_code == 200
    original = initial.json()
    assert original["is_visible_in_app"] is True

    hidden = api.client.patch(
        "/admin/products/1/visibility",
        json={"is_visible_in_app": False, "expected_updated_at": original["updated_at"]},
    )
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["is_visible_in_app"] is False
    with Session(api.engine) as session:
        product = session.get(Product, 1)
        assert product.is_visible_in_app is False
        assert product.archived is False
        assert product.in_stock is True
        assert session.get(Variant, 10).stock == 8

    # Hidden products stay discoverable and editable in the administration catalog.
    listing = api.client.get("/admin/products")
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["is_visible_in_app"] is False
    detail = api.client.get("/admin/products/1").json()
    restored = api.client.patch(
        "/admin/products/1/visibility",
        json={"is_visible_in_app": True, "expected_updated_at": detail["updated_at"]},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["is_visible_in_app"] is True
    with Session(api.engine) as session:
        assert session.get(Product, 1).is_visible_in_app is True

    events = [call.kwargs for call in api.audit.await_args_list]
    assert [event["action"] for event in events] == ["product.visibility.update"] * 2
    assert [(event["entity_type"], event["entity_id"]) for event in events] == [
        ("product", 1), ("product", 1)
    ]
    assert [(event["before"]["is_visible_in_app"], event["after"]["is_visible_in_app"]) for event in events] == [
        (True, False), (False, True)
    ]
    assert [call.args[0] for call in api.cache.bump_namespace.await_args_list] == [
        "catalog", "product", "categories", "catalog", "product", "categories"
    ]


def test_visibility_update_rejects_stale_product_version(visibility_api):
    api = visibility_api
    original = api.client.get("/admin/products/1").json()
    hidden = api.client.patch(
        "/admin/products/1/visibility",
        json={"is_visible_in_app": False, "expected_updated_at": original["updated_at"]},
    )
    assert hidden.status_code == 200

    stale = api.client.patch(
        "/admin/products/1/visibility",
        json={"is_visible_in_app": True, "expected_updated_at": original["updated_at"]},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_record"
    with Session(api.engine) as session:
        assert session.get(Product, 1).is_visible_in_app is False
    assert api.audit.await_count == 1
    assert api.cache.bump_namespace.await_count == 3


@pytest.mark.parametrize("read_only", [False, True])
def test_visibility_update_enforces_write_permissions(visibility_api, monkeypatch, read_only):
    api = visibility_api
    original = api.client.get("/admin/products/1").json()
    if read_only:
        monkeypatch.setattr(admin_permissions, "ADMIN_READ_ONLY", True)
    else:
        api.permissions.remove("catalog.merchandise")

    denied = api.client.patch(
        "/admin/products/1/visibility",
        json={"is_visible_in_app": False, "expected_updated_at": original["updated_at"]},
    )
    assert denied.status_code == (503 if read_only else 403)
    with Session(api.engine) as session:
        assert session.get(Product, 1).is_visible_in_app is True
    api.audit.assert_not_awaited()
    api.cache.bump_namespace.assert_not_awaited()


def test_visibility_update_requires_existing_product_and_valid_payload(visibility_api):
    api = visibility_api
    original = api.client.get("/admin/products/1").json()
    missing = api.client.patch(
        "/admin/products/99/visibility",
        json={"is_visible_in_app": False, "expected_updated_at": original["updated_at"]},
    )
    assert missing.status_code == 404
    invalid = api.client.patch(
        "/admin/products/1/visibility",
        json={"is_visible_in_app": None, "expected_updated_at": original["updated_at"]},
    )
    assert invalid.status_code == 422
    api.audit.assert_not_awaited()
    api.cache.bump_namespace.assert_not_awaited()


def test_catalog_sync_preserves_administrator_visibility_choice(visibility_api):
    api = visibility_api
    original = api.client.get("/admin/products/1").json()
    hidden = api.client.patch(
        "/admin/products/1/visibility",
        json={"is_visible_in_app": False, "expected_updated_at": original["updated_at"]},
    )
    assert hidden.status_code == 200
    with Session(api.engine) as session:
        product = session.get(Product, 1)
        variant = session.get(Variant, 10)
        product.archived = True
        variant.archived = True
        session.commit()
        asyncio.run(
            upsert_catalog_rows(
                AsyncSessionAdapter(session),
                products=[
                    MoySkladProductRow(
                        system_id=product.system_id,
                        sku=product.sku,
                        name="Updated source name",
                        description=None,
                        archived=False,
                    )
                ],
                variants=[
                    MoySkladVariantRow(
                        system_id=variant.system_id,
                        product_system_id=product.system_id,
                        sku=variant.sku,
                        name=variant.name,
                        stock=12,
                        price=variant.price,
                    )
                ],
            )
        )
        session.commit()

    with Session(api.engine) as session:
        product = session.get(Product, 1)
        assert product.is_visible_in_app is False
        assert product.archived is False
        assert product.name == "Updated source name"
        assert session.get(Variant, 10).stock == 12
