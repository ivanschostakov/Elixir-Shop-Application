import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
import httpx

from src.app.services.benefits.settlement_audit import identity_issues
from src.app.services.orders.creation import _build_checkout_snapshot
from src.app.services import orders as order_service
from src.app.services.auth.service import _sync_phone_identity_from_counterparty, _link_moysklad_counterparty_by_email
from src.integrations.moysklad.client import MoySkladClient
from src.integrations.moysklad import order_sync

CID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.parametrize("source", ["draft", "basket"])
def test_order_service_passes_platform_from_request(monkeypatch, source):
    monkeypatch.setattr(order_service, "_sync_runtime_dependencies", lambda: None)
    target = AsyncMock(return_value="created")
    monkeypatch.setattr(order_service._order_creation, f"create_order_from_{source}_for_user", target)
    arguments = {"request": SimpleNamespace(headers={"X-App-Platform": "android"}), "user": SimpleNamespace(id=1), "payment_method": "later"}
    if source == "draft":
        arguments["draft_id"] = 1
    result = asyncio.run(getattr(order_service, f"create_order_from_{source}_for_user")(None, **arguments))
    assert result == "created"
    assert target.await_args.kwargs["client_platform"] == "android"


@pytest.mark.parametrize("platform", ["ios", "android", "web", None, "arbitrary"])
def test_order_snapshot_freezes_validated_platform(platform):
    draft = SimpleNamespace(recipient=SimpleNamespace(name="A", surname="B", phone="test", email="test"), items=[], basket_subtotal=0, comment=None)
    value = _build_checkout_snapshot(draft, payment_method="later", selected_delivery_service="CDEK", selected_delivery_payload={}, client_platform=platform)
    assert value["client_platform"] == (platform if platform in {"ios", "android", "web"} else "unknown")


@pytest.mark.parametrize("platform,expected", [("ios", "iphone"), ("android", "android"), ("web", "telegram"), ("unknown", "legacy"), (None, "legacy")])
def test_channels_use_snapshot_and_keep_legacy_fallback(monkeypatch, platform, expected):
    for name, value in [("IOS", "iphone"), ("ANDROID", "android"), ("TELEGRAM", "telegram")]:
        monkeypatch.setattr(order_sync, f"MOY_SKLAD_{name}_SALES_CHANNEL_HREF", f"https://example.test/{value}")
    monkeypatch.setattr(order_sync, "MOY_SKLAD_SALES_CHANNEL_HREF", "https://example.test/legacy")
    client = SimpleNamespace(find_store_by_name=AsyncMock(return_value=None), find_customerorder_state_by_name=AsyncMock(return_value=None))
    value = asyncio.run(order_sync._resolve_customerorder_refs(client, SimpleNamespace(checkout_snapshot={"client_platform": platform})))
    assert value["sales_channel"]["meta"]["href"] == f"https://example.test/{expected}"


@pytest.mark.parametrize("field,value", [("phone", "+79990000000"), ("email", "a@example.com")])
def test_duplicate_contacts_are_not_auto_linked(monkeypatch, field, value):
    client = MoySkladClient(token="test")
    monkeypatch.setattr(client, "get_page", AsyncMock(return_value={"rows": [{"id": "1", field: value}, {"id": "2", field: value}]}))
    result = asyncio.run(getattr(client, f"get_counterparty_by_{field}")(value))
    assert result is None


def test_phone_search_does_not_use_first_inexact_result(monkeypatch):
    client = MoySkladClient(token="test")
    monkeypatch.setattr(client, "get_page", AsyncMock(return_value={"rows": [{"id": "1", "phone": "+79990000001"}]}))
    assert asyncio.run(client.get_counterparty_by_phone("+79990000000")) is None


def test_phone_login_does_not_replace_an_existing_customer_link():
    user = SimpleNamespace(phone_number="+79990000000", moysklad_counterparty_id=CID)
    assert not _sync_phone_identity_from_counterparty(user, phone_number=user.phone_number, counterparty={"id": str(UUID(int=2))})
    assert user.moysklad_counterparty_id == CID


def test_email_link_rejects_conflicting_phone_without_saving(monkeypatch):
    client = MoySkladClient(token="test")
    monkeypatch.setattr(client, "get_counterparty_by_email", AsyncMock(return_value={"id": str(CID), "phone": "+79990000001"}))
    monkeypatch.setattr("src.app.services.auth.service.get_moysklad_client", lambda: client)
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    user = SimpleNamespace(id=7, email="a@example.com", phone_number="+79990000000", moysklad_counterparty_id=None)
    asyncio.run(_link_moysklad_counterparty_by_email(user, db))
    assert user.moysklad_counterparty_id is None
    db.commit.assert_not_awaited()


def test_shared_card_is_not_rewritten_during_order_sync(monkeypatch):
    client = MoySkladClient(token="test")
    card = {"id": str(CID), "name": "Shared", "externalCode": "website:42", "email": "old@example.test"}
    monkeypatch.setattr(client, "_get_entity_by_id", AsyncMock(return_value=card))
    update = AsyncMock(side_effect=AssertionError("Existing shared cards must not be rewritten"))
    monkeypatch.setattr(client, "_update_entity", update)
    result = asyncio.run(client.resolve_or_sync_counterparty(existing_counterparty_id=CID, external_code="app_user_42", sync_id=CID, name="Recipient", email="new@example.test", phone=None, actual_address=None))
    assert result.counterparty_id == CID
    assert not result.created and not result.updated
    update.assert_not_awaited()


def test_missing_saved_link_requires_manual_review(monkeypatch):
    client = MoySkladClient(token="test")
    monkeypatch.setattr(client, "_get_entity_by_id", AsyncMock(return_value=None))
    create = AsyncMock()
    monkeypatch.setattr(client, "_create_entity", create)
    with pytest.raises(RuntimeError, match="manual relinking"):
        asyncio.run(client.get_or_create_counterparty(existing_counterparty_id=CID, external_code="app_user_42", sync_id=CID, name="A", email=None, phone=None, actual_address=None))
    create.assert_not_awaited()


def test_external_code_search_does_not_match_name_or_first_row(monkeypatch):
    client = MoySkladClient(token="test")
    monkeypatch.setattr(client, "get_page", AsyncMock(return_value={"rows": [{"id": "1", "name": "app_user:42", "externalCode": "website:42"}]}))
    assert asyncio.run(client._find_counterparty("app_user:42")) is None


def test_duplicate_external_code_requires_review(monkeypatch):
    client = MoySkladClient(token="test")
    monkeypatch.setattr(client, "get_page", AsyncMock(return_value={"rows": [{"id": "1", "externalCode": "app:42"}, {"id": "2", "externalCode": "app:42"}]}))
    with pytest.raises(RuntimeError, match="Ambiguous"):
        asyncio.run(client._find_entity_by_external_code("counterparty", "app:42"))


def test_lookup_outage_does_not_create_a_replacement_customer(monkeypatch):
    client = MoySkladClient(token="test")
    response = httpx.Response(503, request=httpx.Request("GET", "https://example.test/entity/counterparty"))
    monkeypatch.setattr(client, "get_page", AsyncMock(side_effect=httpx.HTTPStatusError("unavailable", request=response.request, response=response)))
    create = AsyncMock()
    monkeypatch.setattr(client, "_create_entity", create)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(client.get_or_create_counterparty(existing_counterparty_id=None, external_code="app:42", sync_id=CID, name="A", email=None, phone=None, actual_address=None))
    create.assert_not_awaited()


def test_identity_audit_reports_conflicts_without_personal_data():
    issues = identity_issues({"email": "a@example.com", "phone_number": "+79990000000"}, {"email": "b@example.com", "phone": "+79990000001", "archived": True, "companyType": "legal"}, link_count=2)
    assert set(issues) == {"shared_local_link", "archived_counterparty", "non_individual_counterparty", "email_mismatch", "phone_mismatch"}
    assert identity_issues({"email": "A@example.com"}, {"email": "a@example.com", "companyType": "individual"}, link_count=1) == []


def test_retry_does_not_overwrite_existing_order_positions_or_channel(monkeypatch):
    client = MoySkladClient(token="test")
    monkeypatch.setattr(client, "get_customer_order", AsyncMock(return_value={"id": str(CID)}))
    create = AsyncMock(side_effect=AssertionError("No duplicate order"))
    monkeypatch.setattr(client, "create_customer_order", create)
    result = asyncio.run(client.resolve_or_sync_customerorder(existing_customerorder_id=CID, external_code="order:1", sync_id=CID, organization_id=CID, counterparty_id=CID, positions=[], moment=datetime.now(timezone.utc), description=None, sales_channel={"meta": {"href": "different"}}))
    assert result.customerorder_id == CID and not result.created
    create.assert_not_awaited()
