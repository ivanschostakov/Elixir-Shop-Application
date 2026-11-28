from collections import OrderedDict
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException, Request

import config
from src.app.services.orders import crm, payment_attempt, payments, settlement_payment
from src.integrations.moysklad.client import MoySkladClient
from test_settlement_checkout import CID, CURRENCY, IID, OID, ORG, documents, ref

pytestmark = pytest.mark.anyio
ORDER = f"/entity/customerorder/{OID}"
INVOICE = f"/entity/invoiceout/{IID}"
CURRENCY_PATH = f"/entity/currency/{CURRENCY}"
HREF = "https://example.test/entity/product/test"
FULL_PARAMS = {"expand": "positions.assortment,state,invoicesOut.state", "fields": "stock"}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def case(monkeypatch):
    remote, invoice = documents("123.45", "123.45", 0)
    remote.update(invoicesOut=[ref(IID)], positions={"meta": {"size": 1}, "rows": [
        {"quantity": 1, "reserve": 1, "stock": {"quantity": 3, "reserve": 1},
         "assortment": {"meta": {"type": "product", "href": HREF}}}]})
    rows = {ORDER: remote, INVOICE: invoice, CURRENCY_PATH: {"id": str(CURRENCY), "isoCode": "RUB", "code": "643"}}
    calls, clock = [], [100.]
    def serve(request):
        assert request.method == "GET"
        calls.append((request.url.path, dict(request.url.params)))
        row = rows[request.url.path]
        return row if isinstance(row, httpx.Response) else httpx.Response(200, json=row)

    async with httpx.AsyncClient(base_url="https://example.test", transport=httpx.MockTransport(serve)) as http:
        ms = MoySkladClient(token="test", base_url="https://example.test")
        monkeypatch.setattr(ms, "client", AsyncMock(return_value=http))
        monkeypatch.setattr("src.integrations.moysklad.client.get_moysklad_client", lambda: ms)
        monkeypatch.setattr(settlement_payment, "get_moysklad_client", lambda: ms)
        monkeypatch.setattr(config, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
        monkeypatch.setattr(config, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
        monkeypatch.setattr(payments, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
        monkeypatch.setattr(payment_attempt, "get_cache_service", lambda: SimpleNamespace(client=None))
        monkeypatch.setattr(payment_attempt, "_local_deadlines", OrderedDict())
        monkeypatch.setattr(payment_attempt, "monotonic", lambda: clock[0])
        order = SimpleNamespace(id=123, user_id=5, payment_method="sbp", payment_status="draft",
            payment_provider=None, payment_invoice_id=None, is_paid=False, is_canceled=False,
            moysklad_customerorder_id=OID, moysklad_invoiceout_id=IID, order_code="T1", order_number="T1",
            grand_total=Decimal("123.45"), delivery_total=Decimal(0), recipient=SimpleNamespace(name="A", surname="B", email="a@example.test"),
            checkout_snapshot={"ms_checkout_version": 2, "order_export_version": 1, "benefits": {"use_bonus_rubles": False},
                "stock_reservation": {"status": "exported", "remote_quantities": {HREF: 1}},
                "moysklad_document_identity": {"counterparty_id": str(CID), "organization_id": str(ORG)}})
        session = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(moysklad_counterparty_id=CID)),
            execute=AsyncMock(), commit=AsyncMock())
        async def update(session, order, patch, *, commit):
            for k, v in patch.model_dump(exclude_unset=True).items():
                setattr(order, k, v)
            return order
        monkeypatch.setattr(payments, "update_order", update)
        monkeypatch.setattr(payments, "_resolve_payment_qr_image", AsyncMock(return_value=None))
        gateway = AsyncMock(return_value={"Result": {"InvoiceId": "I-1"}})
        monkeypatch.setattr(payments.intellectmoney, "create_invoice", gateway)
        for method in ("sbp_payment", "get_bank_card_payment_state"):
            monkeypatch.setattr(payments.intellectmoney, method, AsyncMock(return_value={"Result": {"PaymentStep": "Created"}}))
        req = Request({"type": "http", "scheme": "http", "server": ("127.0.0.1", 80), "path": "/", "headers": [],
                       "client": ("127.0.0.1", 1), "query_string": b""})
        async def create(current=None):
            return await payments._create_payment_for_order(session, request=req, order=current or order)
        async def status():
            return await payments.get_payment_status_for_order(session, request=req, order=order)
        yield SimpleNamespace(order=order, create=create, status=status, rows=rows, calls=calls, ms=ms,
                              clock=clock, gateway=gateway, session=session)


async def test_sbp_ref_only_falls_back_then_rechecks_after_success(case):
    new_attempt = deepcopy(case.order)
    result = await case.create()
    assert result["invoice_id"] == "I-1"
    expected = [(ORDER, FULL_PARAMS),
                (INVOICE, {"expand": "state"}), (CURRENCY_PATH, {})]
    assert case.calls == expected
    assert case.gateway.await_args.kwargs["amount_rub"] == Decimal("123.45")
    case.rows[ORDER]["positions"]["rows"][0]["reserve"] = 0
    with pytest.raises(HTTPException, match="Остаток"):
        await case.create(new_attempt)
    assert case.calls == expected + expected[:2]
    case.gateway.assert_awaited_once()


@pytest.mark.parametrize("missing", [None, "attributes", "state", "payedSum", "meta"])
async def test_full_invoice_one_live_get_or_fallback(case, missing):
    invoice = case.rows[INVOICE]
    invoice.update(state={"stateType": "Regular"}, meta={"type": "invoiceout", "href": "https://example.test" + INVOICE})
    nested = deepcopy(invoice)
    if missing:
        del nested[missing]
    case.rows[ORDER]["invoicesOut"] = [nested]
    # Export has warmed the currency identity directory. No order/invoice was read.
    await case.ms.get_currency_identity(CURRENCY)
    assert case.calls == [(CURRENCY_PATH, {})]
    another = deepcopy(case.order)
    assert (await case.create())["invoice_id"] == "I-1"
    expected = [(ORDER, FULL_PARAMS)] + ([(INVOICE, {"expand": "state"})] if missing else [])
    assert case.calls[1:] == expected
    invoice["payedSum"] = 25
    if "payedSum" in nested:
        nested["payedSum"] = 25
    with pytest.raises(HTTPException, match="не совпадает"):
        await case.create(another)
    assert case.calls[1:] == expected * 2
    case.gateway.assert_awaited_once()


@pytest.mark.parametrize("bad", ["bonus", "currency", "payed", "truncated"])
async def test_shared_documents_never_bypass_a_validator(case, bad):
    if bad == "bonus": case.rows[INVOICE]["attributes"][1]["value"] = 1
    if bad == "currency": case.rows[CURRENCY_PATH]["isoCode"] = "USD"
    if bad == "payed": case.rows[INVOICE]["payedSum"] = 1
    if bad == "truncated": case.rows[ORDER]["positions"]["meta"]["size"] = 2
    with pytest.raises(HTTPException) as err:
        await case.create()
    assert err.value.status_code == 409 and isinstance(err.value.detail, str)
    assert not payment_attempt._local_deadlines
    case.gateway.assert_not_awaited()


@pytest.mark.parametrize("path", [ORDER, INVOICE, CURRENCY_PATH])
async def test_429_blocks_repeated_clicks_until_retry_after(case, path):
    original = case.rows[path]
    case.rows[path] = httpx.Response(429, headers={"X-Lognex-Retry-After": "10500"})
    with pytest.raises(HTTPException) as first:
        await case.create()
    assert first.value.detail["retry_after_seconds"] == 11
    calls = list(case.calls)
    case.rows[path] = original
    case.clock[0] += 3.2
    for _ in range(3):
        with pytest.raises(HTTPException) as retry:
            await case.create()
        assert retry.value.detail["retry_after_seconds"] == 8
    case.order.is_canceled = True
    with pytest.raises(HTTPException, match="отменён"):
        await case.create()
    assert case.calls == calls
    case.gateway.assert_not_awaited()
    case.order.is_canceled = False
    case.clock[0] += 7.8
    assert (await case.create())["invoice_id"] == "I-1"
    assert [path for path, _ in case.calls[len(calls):]] == [ORDER, INVOICE, CURRENCY_PATH]


@pytest.mark.parametrize("hold", ["no_link", "missing", "held", "released", "empty", "exported"])
async def test_v2_manager_ack_requires_durable_link_and_hold_no_remote_get(case, hold):
    order = case.order
    order.payment_method, order.payment_status, order.moysklad_invoiceout_id = "later", "pending", None
    reservation = order.checkout_snapshot["stock_reservation"]
    if hold == "no_link": order.moysklad_customerorder_id = None
    elif hold == "missing": del order.checkout_snapshot["stock_reservation"]
    elif hold == "empty": reservation["remote_quantities"] = {}
    else: reservation["status"] = hold
    if hold == "exported":
        assert (await case.create())["payment_status"] == "pending"
        assert (await case.status())["is_paid"] is False
    else:
        for call in (case.create, case.status):
            with pytest.raises(HTTPException) as error:
                await call()
            assert error.value.status_code == 409
            if hold != "released":
                assert error.value.detail["code"] == "settlement_pending"
        assert order.payment_provider is None
    case.gateway.assert_not_awaited()
    assert case.calls == []


def add_settlement(case):
    case.order.checkout_snapshot["settlement_payment"] = {
        "version": 1, "mode": "automatic", "status": "awaiting_invoice", "counterparty_id": str(CID),
        "organization_id": str(ORG), "gross_rubles": "123.45", "maximum_balance_rubles": "0"}
    case.order.checkout_snapshot["benefits"]["stacked_discount_amount"] = 0


async def test_later_unconfirmed_balance_yields_no_amount_and_retries_without_ms(case):
    case.order.payment_method, case.order.payment_status = "later", "pending"
    add_settlement(case)
    case.rows[ORDER]["invoicesOut"] = []
    for call in (case.create, case.create, case.status):
        with pytest.raises(HTTPException) as err:
            await call()
        assert err.value.detail["code"] == "settlement_pending"
        assert "amount_rubles" not in err.value.detail
    assert [p for p, _ in case.calls] == [ORDER, CURRENCY_PATH]
    assert case.order.payment_provider is None
    case.gateway.assert_not_awaited()


async def test_sbp_opt_in_never_substitutes_for_document_verification(case, monkeypatch):
    monkeypatch.setattr(payments, "MOY_SKLAD_ORDER_SYNC_ENABLED", False)
    with pytest.raises(HTTPException) as err:
        await payments._create_payment_for_order(case.session, request=None, order=case.order, accept_pending_amount=True)
    assert err.value.detail["code"] == "settlement_pending"
    case.gateway.assert_not_awaited()


async def test_worker_and_payment_share_only_pending_ttl(case, monkeypatch):
    redis = SimpleNamespace(pttl=AsyncMock(side_effect=[-2, 2100, -2]), set=AsyncMock())
    monkeypatch.setattr(payment_attempt, "get_cache_service", lambda: SimpleNamespace(client=redis))
    add_settlement(case)
    refs = case.rows[ORDER].pop("invoicesOut")
    with pytest.raises(HTTPException):
        async with payment_attempt.payment_backoff(case.order.id, "sbp"):
            await settlement_payment.prepare_settlement_payment(case.session, order=case.order)
    key = redis.pttl.await_args.args[0]
    redis.set.assert_awaited_once_with(key, "1", ex=4)
    assert not payment_attempt._local_deadlines
    case.rows[ORDER]["invoicesOut"] = refs
    calls = list(case.calls)
    with pytest.raises(HTTPException) as retry:
        await case.create()
    assert retry.value.detail["retry_after_seconds"] == 3
    assert case.calls == calls
    case.rows[INVOICE]["payedSum"] = 1
    with pytest.raises(HTTPException) as invalid:
        await case.create()
    assert isinstance(invalid.value.detail, str)
    assert [p for p, _ in case.calls[len(calls):]] == [ORDER, INVOICE]
    case.gateway.assert_not_awaited()
    redis.set.assert_awaited_once()


async def test_settlement_rechecks_stock_after_commit_and_crm(case, monkeypatch):
    add_settlement(case)
    case.session.execute.return_value = SimpleNamespace(scalar_one=lambda: SimpleNamespace(calculation_snapshot={}))
    async def change_stock(session, order):
        session.commit.assert_awaited_once()
        case.rows[ORDER]["positions"]["rows"][0]["stock"]["quantity"] = 0
    monkeypatch.setattr(crm, "sync_settlement_amount_to_crm", change_stock)
    with pytest.raises(HTTPException, match="Остаток"):
        await case.create()
    assert [p for p, _ in case.calls] == [ORDER, CURRENCY_PATH, INVOICE, ORDER]
    assert case.calls[-1][1]["fields"] == "stock"
    case.gateway.assert_not_awaited()
