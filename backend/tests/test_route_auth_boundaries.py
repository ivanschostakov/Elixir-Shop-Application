import uuid

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import src.app.services.admin.permissions as admin_permissions
import src.app.modules.product_categories.router as product_categories_router_module
import src.app.modules.products.router as products_router_module
import src.app.modules.requisites.router as requisites_router_module
from src.app.main import app
from config import ufa_now
from src.app.services.admin.security import create_admin_access_token
from src.app.services.security import create_access_token
from src.database import get_db
from src.database.models import AdminIdentity


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/favorites/products", None),
        ("GET", "/api/v1/users/me/basket", None),
        ("GET", "/api/v1/users/me/order-drafts", None),
        ("GET", "/api/v1/users/me/order-drafts/latest", None),
        ("GET", "/api/v1/users/me/search-queries", None),
        ("GET", "/api/v1/users/me/ai-chat", None),
        ("GET", "/api/v1/users/me/community/status", None),
        ("GET", "/api/v1/users/me/community/topics", None),
        ("GET", "/api/v1/users/me/community/topics/1/messages", None),
        ("POST", "/api/v1/users/me/ai-chat", {"text": "hello"}),
        ("POST", "/api/v1/users/me/community/topics/1/read", {"last_message_id": 1}),
        ("POST", "/api/v1/users/me/search-queries", {"query": "peptide"}),
        ("DELETE", "/api/v1/users/me/search-queries", None),
        ("POST", "/api/v1/users/me/ai-chat/actions", {"message_id": 1, "action_id": "a", "action_token": "t"}),
        ("PATCH", "/api/v1/users/me/order-drafts/1", {}),
        ("DELETE", "/api/v1/users/me/order-drafts/1", None),
        ("POST", "/api/v1/users/me/basket/restore-draft/1", None),
        ("POST", "/api/v1/users/me/orders/1/repeat", None),
        (
            "POST",
            "/api/v1/products",
            {
                "sku": "protected-sku",
                "name": "Protected Product",
                "description": None,
                "usage": None,
                "expiration": None,
                "priority": 0,
            },
        ),
        ("PATCH", "/api/v1/products/1", {}),
        ("DELETE", "/api/v1/products/1", None),
        ("POST", "/api/v1/requisites", {"title": "R", "config": {"label": "value"}}),
        ("PATCH", "/api/v1/requisites/1", {"title": "Updated"}),
        ("DELETE", "/api/v1/requisites/1", None),
    ],
)
def test_protected_routes_require_authentication(client: TestClient, method: str, path: str, payload: dict | None):
    request_kwargs = {"json": payload} if payload is not None else {}
    response = client.request(method, path, **request_kwargs)

    assert response.status_code == 401, response.text


def test_products_get_is_public(monkeypatch: pytest.MonkeyPatch):
    async def fake_get_db():
        yield SimpleNamespace(get=AsyncMock(return_value=None))

    async def fake_get_products(*args, **kwargs):
        return []

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(products_router_module, "get_products", fake_get_products)

    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/products")

        assert response.status_code == 200, response.text
        assert response.json() == []
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_product_categories_get_is_public(monkeypatch: pytest.MonkeyPatch):
    async def fake_get_db():
        yield object()

    async def fake_get_product_categories(*args, **kwargs):
        return []

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(product_categories_router_module, "get_product_categories", fake_get_product_categories)

    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/product-categories")

        assert response.status_code == 200, response.text
        assert response.json() == []
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_requisites_get_is_public(monkeypatch: pytest.MonkeyPatch):
    async def fake_get_db():
        yield object()

    async def fake_get_requisites(*args, **kwargs):
        return []

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(requisites_router_module, "get_requisites", fake_get_requisites)

    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/requisites")

        assert response.status_code == 200, response.text
        assert response.json() == []
    finally:
        app.dependency_overrides.pop(get_db, None)


def _product_payload(sku: str = "admin-only-sku") -> dict:
    return {
        "sku": sku,
        "name": "Admin Only Product",
        "description": None,
        "usage": None,
        "expiration": None,
        "priority": 0,
    }


def _fake_admin_identity() -> AdminIdentity:
    return AdminIdentity(
        id=123,
        email="catalog-user@example.com",
        password_hash="hash",
        name="Catalog",
        surname="User",
        is_active=True,
    )


@pytest.fixture
def admin_headers(monkeypatch: pytest.MonkeyPatch, request):
    now = ufa_now()
    session = SimpleNamespace(
        admin_user_id=123,
        mfa_verified_at=now,
        revoked_at=None,
        expires_at=now + timedelta(hours=1),
    )
    admin = SimpleNamespace(
        user=_fake_admin_identity(), is_active=True, mfa_confirmed_at=now, role_assignments=[]
    )
    session_state = getattr(request, "param", "valid")
    if session_state == "revoked":
        session.revoked_at = now
    elif session_state == "expired":
        session.expires_at = now - timedelta(seconds=1)
    elif session_state == "without_mfa":
        session.mfa_verified_at = None

    async def fake_get_db():
        yield SimpleNamespace(get=AsyncMock(return_value=session))

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(admin_permissions, "get_admin_by_user_id", AsyncMock(return_value=admin))
    try:
        token = create_admin_access_token(user_id=123, session_id=456)
        yield {"Authorization": f"Bearer {token}"}
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize("admin_headers", ["revoked", "expired", "without_mfa"], indirect=True)
def test_product_create_rejects_invalid_admin_session(monkeypatch, admin_headers):
    create_product = AsyncMock()
    monkeypatch.setattr(products_router_module, "create_product", create_product)
    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/products", json=_product_payload(), headers=admin_headers)
    assert response.status_code == 401, response.text
    create_product.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", "/api/v1/products", _product_payload()),
        ("PATCH", "/api/v1/products/1", {"name": "Updated"}),
        ("DELETE", "/api/v1/products/1", None),
        ("POST", "/api/v1/requisites", {"title": "R", "config": {"label": "value"}}),
        ("PATCH", "/api/v1/requisites/1", {"title": "Updated"}),
        ("DELETE", "/api/v1/requisites/1", None),
    ],
)
def test_product_mutations_reject_authenticated_non_admin(method: str, path: str, payload: dict | None):
    async def fake_get_db():
        yield object()

    app.dependency_overrides[get_db] = fake_get_db
    token = create_access_token(user_id=123, session_id=456)

    try:
        with TestClient(app) as test_client:
            request_kwargs = {"json": payload} if payload is not None else {}
            response = test_client.request(method, path, headers={"Authorization": f"Bearer {token}"}, **request_kwargs)

        assert response.status_code == 401, response.text
        assert response.json()["detail"] == "Could not validate admin credentials"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_product_create_allows_admin(monkeypatch: pytest.MonkeyPatch, admin_headers):
    async def fake_create_product(*args, **kwargs):
        return SimpleNamespace(id=777)

    async def fake_get_product_by_id(*args, **kwargs):
        return SimpleNamespace(id=777)

    async def fake_get_product_review_stats(*args, **kwargs):
        return {}

    def fake_serialize_product_with_variants(*args, **kwargs):
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": 777,
            "system_id": str(uuid.uuid4()),
            "sku": "admin-only-sku",
            "name": "Admin Only Product",
            "description": None,
            "usage": None,
            "expiration": None,
            "priority": 0,
            "in_stock": False,
            "archived": False,
            "image_url": "http://testserver/media/products/product.png",
            "created_at": now,
            "updated_at": now,
            "variants": [],
        }

    monkeypatch.setattr(products_router_module, "create_product", fake_create_product)
    monkeypatch.setattr(products_router_module, "get_product_by_id", fake_get_product_by_id)
    monkeypatch.setattr(products_router_module, "get_product_review_stats", fake_get_product_review_stats)
    monkeypatch.setattr(products_router_module, "serialize_product_with_variants", fake_serialize_product_with_variants)

    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/products", json=_product_payload(), headers=admin_headers)

    assert response.status_code == 201, response.text
    assert response.json()["id"] == 777


def test_requisite_create_allows_admin(monkeypatch: pytest.MonkeyPatch, admin_headers):
    async def fake_create_requisite(*args, **kwargs):
        now = datetime.now(timezone.utc)
        return SimpleNamespace(
            id=888,
            title="Тестовый реквизит",
            config={"ИНН": "000000000000"},
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(requisites_router_module, "create_requisite", fake_create_requisite)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/requisites",
            json={"title": "Тестовый реквизит", "config": {"ИНН": "000000000000"}},
            headers=admin_headers,
        )

    assert response.status_code == 201, response.text
    assert response.json()["id"] == 888
    assert response.json()["config"]["ИНН"] == "000000000000"
