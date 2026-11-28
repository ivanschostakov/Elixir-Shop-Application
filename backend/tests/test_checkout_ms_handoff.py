import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException

from src.integrations.moysklad.client import MoySkladClient
from src.integrations.moysklad.order_sync import service


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def checkout(monkeypatch):
    org, buyer, oid, iid, sku = [UUID(int=n) for n in range(1, 6)]
    client = MoySkladClient(token="test", base_url="https://ms.test")
    def ref(kind, key):
        return {"meta": {"type": kind, "href": f"https://ms.test/entity/{kind}/{key}", "mediaType": "application/json"}}
    line = SimpleNamespace(variant_id=1, product_name="Item", quantity=1, unit_price=Decimal(10), line_total=Decimal(10))
    buyer_row = SimpleNamespace(id=1, moysklad_counterparty_id=buyer)
    order = SimpleNamespace(id=22, order_code="EP-TEST", items=[line], basket_subtotal=Decimal(10),
        grand_total=Decimal(10), delivery_total=Decimal(0), recipient=None, delivery_address=None,
        delivery_string=None, selected_delivery_payload={}, selected_delivery_service="CDEK", comment=None,
        checkout_snapshot={"order_export_version": 1, "ms_checkout_version": 2, "ms_buyer_at_checkout": str(buyer),
            "benefits": {"applications": []}, "stock_reservation": {"status": "held", "quantities": {"1": 1}}},
        payment_method="later", payment_provider="manager", is_canceled=False, created_at=datetime.now(timezone.utc),
        amocrm_lead_id=None, moysklad_customerorder_id=None, moysklad_invoiceout_id=None)
    db = SimpleNamespace(execute=AsyncMock(), refresh=AsyncMock(), flush=AsyncMock(), commit=AsyncMock())
    state = SimpleNamespace(calls=[], posted=None, first_response=200, missing=False, invoice=False,
        wrong_buyer=False, wrong_sum=False, reserve_ok=True, inline=True, linked_invoice_id=iid)
    def respond(request):
        path = request.url.path
        state.calls.append((request.method, path))
        if path == f"/entity/currency/{sku}":
            return httpx.Response(200, json={"id":str(sku), "isoCode":"RUB", "code":"643"})
        if request.method == "POST" and path == "/entity/customerorder":
            assert order.checkout_snapshot["ms_post_status"] == "submitted"
            body = json.loads(request.content)
            if state.first_response == 429:
                return httpx.Response(429)
            state.posted = {**body, "id": str(oid), "sum": 1000, "applicable": True,
                "positions": {"rows": body["positions"], "meta": {"size": len(body["positions"])}}}
            if state.first_response == "timeout":
                raise httpx.ReadTimeout("lost reply", request=request)
            return httpx.Response(200, json=state.posted)
        if path == "/entity/customerorder":
            return httpx.Response(200, json={"rows": [] if state.missing else [state.posted]})
        invoice = {**ref("invoiceout", iid), "id": str(iid), "sum": 1000, "applicable": True, "payedSum": 0,
            "state": {"stateType": "Regular"}, "rate": {"value": 1, "currency": ref("currency", sku)},
            "attributes": [], "customerOrder": ref("customerorder", oid), "agent": ref("counterparty", buyer),
            "organization": ref("organization", org)}
        invoice["meta"]["href"] += "?expand=state"
        if path == f"/entity/invoiceout/{iid}":
            return httpx.Response(200, json=invoice)
        assert path == f"/entity/customerorder/{oid}"
        data = {**state.posted, "rate": invoice["rate"], "payedSum": 0, "invoicesOut": [invoice if state.inline else ref("invoiceout", iid)] if state.invoice else []}
        if request.url.params.get("fields") == "stock":
            for row in data["positions"]["rows"]:
                row["stock"] = {"quantity": 4, "reserve": 1}
        if state.wrong_buyer: data["agent"] = ref("counterparty", sku)
        if state.wrong_sum: data["sum"] += 1
        if not state.reserve_ok: data["positions"]["rows"][0]["reserve"] = 0
        return httpx.Response(200, json=data)
    client._client = httpx.AsyncClient(base_url="https://ms.test", transport=httpx.MockTransport(respond))
    monkeypatch.setattr(service, "get_moysklad_client", lambda: client)
    monkeypatch.setattr(service, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    monkeypatch.setattr(service, "_resolve_organization_id", AsyncMock(return_value=org))
    monkeypatch.setattr(service, "_resolve_customerorder_refs", AsyncMock(return_value={
        "state":ref("state",sku), "store":ref("store",sku), "sales_channel":ref("saleschannel",sku)}))
    monkeypatch.setattr(service, "_load_assortment_refs", AsyncMock(return_value={1: ("variant",sku)}))
    monkeypatch.setattr(service, "_moysklad_custom_attr_refs", AsyncMock(return_value={
        "payment_method":"https://ms.test/method", "delivery_method":"https://ms.test/delivery"}))
    monkeypatch.setattr(service, "_shipment_address_full", AsyncMock(return_value=None))
    monkeypatch.setattr("src.app.services.orders.crm.sync_moysklad_document_links", AsyncMock())
    async def ack(_, obj, *, remote_quantities):
        obj.checkout_snapshot["stock_reservation"].update(status="exported", remote_quantities=remote_quantities)
    monkeypatch.setattr("src.app.services.orders.stock_reservations.acknowledge_remote_reservation", ack)
    async def export():
        return await service.sync_order_to_moysklad(db, order=order, user=buyer_row)
    return state, order, export, client


@pytest.mark.anyio
@pytest.mark.parametrize("method,invoice,inline,count", [
    ("later", False, False, 2), ("sbp", True, True, 2), ("sbp", True, False, 3)])
async def test_export_call_budget_and_optional_invoice(checkout, method, invoice, inline, count):
    state, order, export, client = checkout
    order.payment_method = method
    state.invoice, state.inline = invoice, inline
    await export()
    assert len(state.calls) == count
    assert state.calls[0] == ("POST", "/entity/customerorder")
    assert order.checkout_snapshot["stock_reservation"]["status"] == "exported"
    assert order.moysklad_invoiceout_id == (state.linked_invoice_id if invoice else None)
    await client.aclose()


@pytest.mark.anyio
async def test_three_ms_requests_through_returned_qr(monkeypatch, checkout):
    import config
    from src.app.services.orders import payments, invoice_preparation
    state, order, export, ms = checkout
    order.payment_method, order.payment_provider, order.payment_status = "sbp", None, "draft"
    order.order_number, order.payment_invoice_id, order.is_paid = "EP-TEST", None, False
    order.checkout_snapshot["benefits"]["use_bonus_rubles"] = False
    state.invoice = True
    await ms.get_currency_identity(UUID(int=5))
    state.calls.clear()
    await export()
    order.recipient = SimpleNamespace(name="Test", surname="Buyer", email="test@example.test")
    for obj in (config, payments):
        monkeypatch.setattr(obj, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    monkeypatch.setattr(config, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    monkeypatch.setattr("src.integrations.moysklad.client.get_moysklad_client", lambda: ms)
    monkeypatch.setattr(payments, "_intellectmoney_urls", lambda *_: dict.fromkeys(
        ["success_url","fail_url","back_url","result_url"], "https://example.test"))
    monkeypatch.setattr(payments, "_detect_request_ip", lambda _: "127.0.0.1")
    async def update(_, row, patch, **kwargs):
        for key, value in patch.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        return row
    monkeypatch.setattr(payments, "update_order", update)
    monkeypatch.setattr(payments.intellectmoney, "create_invoice", AsyncMock(return_value={"InvoiceId":"test-invoice"}))
    qr = {"payment_step":"Created","qr_url":"https://example.test/test-qr","qr_image":None}
    monkeypatch.setattr(payments.intellectmoney, "sbp_payment", AsyncMock(return_value=qr))
    monkeypatch.setattr(payments.intellectmoney, "get_bank_card_payment_state", AsyncMock(return_value=qr))
    monkeypatch.setattr(payments.intellectmoney, "parse_payment_state", lambda response: response)
    monkeypatch.setattr(payments, "_resolve_payment_qr_image", AsyncMock(return_value=None))
    monkeypatch.setattr(payments, "_move_lead_to_pending_payment", AsyncMock(return_value=order))
    queued = AsyncMock()
    monkeypatch.setattr(invoice_preparation, "queue_invoice_sent", queued)
    payload = await payments._create_payment_for_order(None, request=None, order=order, payment_method="sbp")
    assert payload["qr_url"] == qr["qr_url"]
    assert state.calls == [("POST","/entity/customerorder"), ("GET",f"/entity/customerorder/{order.moysklad_customerorder_id}"),
                           ("GET",f"/entity/customerorder/{order.moysklad_customerorder_id}")]
    queued.assert_awaited_once()
    await ms.aclose()


@pytest.mark.anyio
@pytest.mark.parametrize("visible", [True, False])
async def test_lost_post_response_never_posts_again(checkout, visible):
    state, order, export, client = checkout
    state.first_response = "timeout"
    with pytest.raises(httpx.ReadTimeout):
        await export()
    assert order.checkout_snapshot["stock_reservation"]["status"] == "held"
    state.missing = not visible
    if visible:
        await export()
        assert order.moysklad_customerorder_id
    else:
        with pytest.raises(HTTPException, match="reconcile"):
            await export()
        assert order.moysklad_customerorder_id is None
    assert sum(m == "POST" for m, _ in state.calls) == 1
    await client.aclose()


@pytest.mark.anyio
async def test_explicit_throttling_allows_retry_with_same_identity(checkout):
    state, order, export, client = checkout
    state.first_response = 429
    with pytest.raises(httpx.HTTPStatusError): await export()
    assert order.checkout_snapshot["ms_post_status"] == "rejected"
    state.first_response = 200
    await export()
    assert state.posted["externalCode"] and state.posted["syncId"]
    assert order.moysklad_customerorder_id
    await client.aclose()


@pytest.mark.anyio
@pytest.mark.parametrize("change", ["wrong_buyer", "reserve_unavailable", "wrong_sum"])
async def test_changed_order_never_acknowledged(checkout, change):
    state, order, export, client = checkout
    state.wrong_buyer, state.reserve_ok = change == "wrong_buyer", change != "reserve_unavailable"
    state.wrong_sum = change == "wrong_sum"
    with pytest.raises(HTTPException if state.wrong_sum else ValueError): await export()
    assert order.checkout_snapshot["stock_reservation"]["status"] == "held"
    assert not order.moysklad_invoiceout_id
    await client.aclose()


@pytest.mark.anyio
async def test_invoice_post_guard_survives_loss_of_response():
    db = SimpleNamespace(execute=AsyncMock(), refresh=AsyncMock(), commit=AsyncMock())
    order = SimpleNamespace(id=7, is_canceled=False, moysklad_invoiceout_id=None,
                            checkout_snapshot={"stock_reservation": {"status": "exported"}})
    await service._claim_invoice_post(db, order)
    db.commit.assert_awaited_once()
    with pytest.raises(HTTPException, match="reconciliation"):
        await service._claim_invoice_post(db, order)


@pytest.mark.anyio
async def test_one_durable_robot_job_even_if_export_repeats():
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from src.app.services.orders.invoice_preparation import queue_invoice_preparation
    from src.database import engine
    from src.database.models import IntegrationRun
    order = SimpleNamespace(id=uuid4().int % (2**62))
    isolated = create_async_engine(engine.url, poolclass=NullPool)
    async with async_sessionmaker(isolated)() as db:
        await queue_invoice_preparation(db, order)
        await queue_invoice_preparation(db, order)
        assert await db.scalar(select(func.count()).select_from(IntegrationRun).where(
            IntegrationRun.idempotency_key == f"ms:prepare-robot-invoice:{order.id}")) == 1
        await db.rollback()
    await isolated.dispose()


@pytest.mark.anyio
async def test_robot_wait_does_not_charge_or_recreate_order(monkeypatch):
    from src.app.services.admin.jobs import retry_delay_for_error
    from src.app.services.orders import settlement_payment as settlement
    from src.app.services.orders.invoice_preparation import InvoicePreparationPending, prepare_robot_invoice
    from src.app.services.orders import payments
    @asynccontextmanager
    async def lock(*args, **kwargs):
        yield
    monkeypatch.setattr(settlement, "settlement_lock", lock)
    gateway = AsyncMock(side_effect=AssertionError("Background wait cannot start a payment"))
    monkeypatch.setattr(payments.intellectmoney, "create_invoice", gateway)
    attempt = AsyncMock(side_effect=HTTPException(409, {"code":"settlement_pending", "retry_after_seconds":71}))
    monkeypatch.setattr(settlement, "prepare_settlement_payment", attempt)
    order = SimpleNamespace(id=uuid4().int % (2**62), is_paid=False, is_canceled=False, payment_status="pending", payment_method="later",
        moysklad_customerorder_id=uuid4(),checkout_snapshot={"stock_reservation":{"status":"exported"},
        "settlement_payment":{"version":1,"status":"awaiting_invoice","counterparty_id":str(uuid4())}})
    db = SimpleNamespace(refresh=AsyncMock())
    with pytest.raises(InvoicePreparationPending) as err:
        await prepare_robot_invoice(db, order)
    assert retry_delay_for_error(err.value, 1) == 71
    order.is_canceled = True
    assert (await prepare_robot_invoice(db, order))["skipped"] == "no_longer_waiting"
    attempt.assert_awaited_once()
    gateway.assert_not_awaited()
