import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException

from src.app.services.admin.jobs import is_retryable_error, retry_delay_for_error
from src.app.services.orders.common import _require_recipient_phone
from src.app.services.orders.crm import _format_order_for_amocrm
from src.app.services.orders import creation
from src.integrations.moysklad import order_sync
from src.integrations.moysklad.client import MoySkladClient
from src.integrations.moysklad.schemas import MoySkladCustomerOrderSyncResult, MoySkladCounterpartySyncResult, MoySkladInvoiceOutSyncResult


ENTITY_ID = UUID("11111111-1111-4111-8111-111111111111")
INVOICE_ID = UUID("22222222-2222-4222-8222-222222222222")


def make_order(prices, quantities, total, delivery, applications=None):
    items = [SimpleNamespace(variant_id=i + 1, product_name=f"Product {i}", quantity=q, unit_price=Decimal(p), line_total=Decimal(p) * q) for i, (p, q) in enumerate(zip(prices, quantities))]
    subtotal = sum((i.line_total for i in items), Decimal(0))
    return SimpleNamespace(
        id=22, order_code="EP-TEST", items=items, basket_subtotal=subtotal,
        grand_total=Decimal(total), delivery_total=Decimal(delivery),
        checkout_snapshot={"benefits": {"applications": applications or []}},
        comment=None, recipient=None, delivery_address=None, delivery_string=None,
        selected_delivery_payload={}, selected_delivery_service="CDEK",
        created_at=datetime(2026, 10, 6, tzinfo=timezone.utc),
        payment_method="sbp", payment_provider="intellectmoney", payment_status="created",
        moysklad_customerorder_id=None, moysklad_invoiceout_id=None,
        amocrm_lead_id=None,
    )


@pytest.mark.parametrize("prices,quantities,total,delivery,expected", [
    (["4890"], [2], "8902.52", "415.92", 848660),
    (["380", "2690"], [2, 5], "13580.82", "370.82", 1321000),
    (["0.03", "0.04"], [3, 2], "0.11", "0", 11),
    (["100"], [3], "0", "0", 0),
    (["4890"], [2], "10195.92", "415.92", 978000),
])
def test_moysklad_positions_preserve_exact_net_total_and_quantities(prices, quantities, total, delivery, expected):
    order = make_order(prices, quantities, total, delivery)
    client = MoySkladClient(token="test")
    refs = {i.variant_id: ("variant", UUID(int=i.variant_id)) for i in order.items}
    positions, missing = order_sync._build_customerorder_positions(moysklad_client=client, assortment_refs=refs, order=order)
    assert not missing
    assert sum(Decimal(str(p["price"])) * Decimal(str(p["quantity"])) for p in positions) == expected
    assert all(p["discount"] == 0 for p in positions)
    for item in order.items:
        assert sum(p["quantity"] for p in positions if p["assortment"]["meta"]["href"].endswith(str(UUID(int=item.variant_id)))) == item.quantity


def test_inconsistent_totals_do_not_produce_moysklad_positions():
    order = make_order(["10"], [1], "11", "0")
    with pytest.raises(ValueError, match="inconsistent"):
        order_sync._build_customerorder_positions(moysklad_client=MoySkladClient(token="test"), assortment_refs={1: ("variant", ENTITY_ID)}, order=order)


@pytest.mark.parametrize("subtotal,total,delivery,applications", [
    ("9780", "8902.52", "415.92", [{"source_kind": "bitrix_promo", "code": "Elena", "discount_amount": "293.40"}, {"source_kind": "moysklad_bonus", "discount_amount": "1000"}]),
    ("14210", "13580.82", "370.82", [{"source_kind": "moysklad_bonus", "discount_amount": "1000"}]),
])
def test_crm_note_uses_persisted_total_with_discount_breakdown(subtotal, total, delivery, applications):
    payload = {"checkout_data": {"total": subtotal, "items": []}, "benefits": {"applications": applications, "total_after_discounts": "99999"}}
    note = _format_order_for_amocrm("EP-TEST", payload, "CDEK", None, "", Decimal(delivery), grand_total=Decimal(total), order_date=datetime(2026, 10, 4))
    assert f"Итого к оплате: {total}" in note
    assert "Бонусы: -1000.00" in note
    assert "Дата заказа: 04.10.2026" in note
    if len(applications) == 2: assert "Elena: -293.40" in note


@pytest.mark.parametrize("phone", [None, "", "123", "+7abc9999999", "0000000000000000"])
def test_checkout_rejects_missing_or_invalid_phone(phone):
    with pytest.raises(HTTPException) as exc:
        _require_recipient_phone(phone)
    assert exc.value.status_code == 422


def test_checkout_accepts_formatted_phone():
    assert _require_recipient_phone("+7 (913) 537-23-98") == "+79135372398"


@pytest.mark.parametrize("source", ["basket", "draft"])
def test_phone_is_checked_before_stock_quotes_and_order_creation(monkeypatch, source):
    value = SimpleNamespace(id=1, items=[object()], recipient=SimpleNamespace(phone=""), delivery_address=object())
    user = SimpleNamespace(id=44)
    async def get(*args, **kwargs): return value
    async def no_existing(*args, **kwargs): return None
    session = SimpleNamespace()
    if source == "basket":
        monkeypatch.setattr(creation, "get_basket_by_user_id", get)
        call = creation.create_order_from_basket_for_user(session, user=user, payment_method="sbp")
    else:
        monkeypatch.setattr(creation, "get_order_draft_by_id", get)
        monkeypatch.setattr(creation, "get_order_by_draft_id", no_existing)
        call = creation.create_order_from_draft_for_user(session, user=user, draft_id=1, payment_method="sbp")
    with pytest.raises(HTTPException) as exc: asyncio.run(call)
    assert exc.value.status_code == 422


@pytest.mark.parametrize("status", [429, 500, 503])
def test_lookup_errors_never_mean_document_does_not_exist(monkeypatch, status):
    client = MoySkladClient(token="test")
    async def fail(*args, **kwargs):
        response = httpx.Response(status, request=httpx.Request("GET", "https://example.test/entity/customerorder"))
        response.raise_for_status()
    monkeypatch.setattr(client, "get_page", fail)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(client._find_entity_by_external_code("customerorder", "app_order:22"))


def test_duplicate_external_codes_require_manual_review(monkeypatch):
    client = MoySkladClient(token="test")
    async def get(*args, **kwargs):
        return {"rows": [{"id": "1", "externalCode": "app_order:22"}, {"id": "2", "externalCode": "app_order:22"}]}
    monkeypatch.setattr(client, "get_page", get)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(client._find_entity_by_external_code("customerorder", "app_order:22"))
    assert exc.value.status_code == 409


def test_existing_document_with_wrong_total_is_not_rewritten():
    with pytest.raises(HTTPException) as exc:
        MoySkladClient._validate_document_sum({"id": "existing", "sum": 848708}, [{"price": 424330, "quantity": 2, "discount": 0}])
    assert exc.value.status_code == 409
    assert "manual review" in exc.value.detail


def test_rate_limit_retry_waits_for_retry_after():
    response = httpx.Response(429, headers={"Retry-After": "120"}, request=httpx.Request("GET", "https://example.test"))
    error = httpx.HTTPStatusError("rate limit", request=response.request, response=response)
    assert is_retryable_error(error)
    assert retry_delay_for_error(error, 1) == 120
    assert not is_retryable_error(HTTPException(status_code=409, detail="manual review"))


def test_first_retry_deadline_is_persisted_so_queue_recovery_does_not_skip_delay(monkeypatch):
    import src.app.services.admin.jobs as jobs
    calls = []
    class Session:
        async def execute(self, *args): return SimpleNamespace(scalar_one_or_none=lambda: None)
        def add(self, run): self.run = run
        async def flush(self): self.run.id = 1
        async def commit(self): pass
    async def enqueue(run_id, **kwargs): calls.append((run_id, kwargs))
    monkeypatch.setattr(jobs, "enqueue_integration_run", enqueue)
    response = httpx.Response(429, headers={"Retry-After": "120"}, request=httpx.Request("GET", "https://example.test"))
    error = httpx.HTTPStatusError("rate limit", request=response.request, response=response)
    started = datetime.now(timezone.utc)
    run = asyncio.run(order_sync._record_automatic_order_sync(Session(), order_id=22, status="queued", enqueue=True, retry_error=error))
    assert (run.next_attempt_at - started).total_seconds() >= 120
    assert calls == [(1, {"delay_seconds": 120})]


def test_customerorder_id_is_committed_before_invoice_failure_and_reused(monkeypatch):
    order = make_order(["4890"], [2], "8902.52", "415.92")
    user = SimpleNamespace(id=47, moysklad_counterparty_id=ENTITY_ID, name="Test", surname="User", email="test@example.test", phone_number="+79990000000")
    committed = []
    class Session:
        async def execute(self, *args): pass
        async def refresh(self, *args, **kwargs): pass
        async def flush(self): pass
        async def commit(self): committed.append((order.moysklad_customerorder_id, order.moysklad_invoiceout_id))
    class Client(MoySkladClient):
        fail_invoice = True
        customer_creates = 0
        async def resolve_or_sync_counterparty(self, **kwargs):
            return MoySkladCounterpartySyncResult(counterparty_id=ENTITY_ID, external_code="app_user:47", created=False, updated=False)
        async def resolve_or_sync_customerorder(self, **kwargs):
            exists = kwargs["existing_customerorder_id"] is not None
            if not exists: self.customer_creates += 1
            return MoySkladCustomerOrderSyncResult(customerorder_id=ENTITY_ID, external_code="app_order:22", created=not exists)
        async def resolve_or_sync_invoiceout(self, **kwargs):
            assert committed[0] == (ENTITY_ID, None)
            if self.fail_invoice: raise TimeoutError("invoice failed")
            return MoySkladInvoiceOutSyncResult(invoiceout_id=INVOICE_ID, external_code="app_order:22:invoiceout", created=True)
        def build_customerorder_attributes(self, **kwargs): return []
    client = Client(token="test")
    async def organization(*args): return ENTITY_ID
    async def assortment(*args, **kwargs): return {1: ("variant", ENTITY_ID)}
    async def refs(*args): return {"store": {}, "state": {}, "sales_channel": {}}
    async def empty(*args, **kwargs): return {}
    monkeypatch.setattr(order_sync, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    monkeypatch.setattr(order_sync, "get_moysklad_client", lambda: client)
    monkeypatch.setattr(order_sync, "_resolve_organization_id", organization)
    monkeypatch.setattr(order_sync, "_load_assortment_refs", assortment)
    monkeypatch.setattr(order_sync, "_resolve_customerorder_refs", refs)
    monkeypatch.setattr(order_sync, "_moysklad_custom_attr_refs", empty)
    monkeypatch.setattr(order_sync, "_shipment_address_full", empty)
    with pytest.raises(TimeoutError): asyncio.run(order_sync.sync_order_to_moysklad(Session(), order=order, user=user))
    assert order.moysklad_customerorder_id == ENTITY_ID
    client.fail_invoice = False
    asyncio.run(order_sync.sync_order_to_moysklad(Session(), order=order, user=user))
    assert client.customer_creates == 1
    assert committed[-1] == (ENTITY_ID, INVOICE_ID)
