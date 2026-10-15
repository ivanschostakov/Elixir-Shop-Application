import asyncio
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from test_settlement_checkout import CID, CURRENCY, IID, OID, ORG, documents, ref
from src.app.services.orders import settlement_payment as service
from src.app.services.benefits import moysklad_bonus
from src.integrations.moysklad.settlement_checkout import (
    SOURCE_KIND, SettlementNotReady, check_open_settlement_orders, verify_ruble_currency,
)


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.mark.parametrize("other,blocked", [
    ({"sum": 10000, "shippedSum": 0}, True),
    ({"sum": 10000, "shippedSum": 9999, "payedSum": 10000}, True),
    ({"sum": 10000, "shippedSum": 10000}, False),
    ({"sum": 10000, "state": {"stateType": "Unsuccessful"}}, False),
    ({"sum": 10000, "applicable": False}, False),
])
def test_external_pending_orders_block_repeated_balance_use(other, blocked):
    client = SimpleNamespace(entity_href=lambda *args: "https://example.test/agent",
        get_page=AsyncMock(return_value={"rows": [{"id": str(OID), **other}]}))
    if blocked:
        with pytest.raises(SettlementNotReady):
            run(check_open_settlement_orders(client, CID))
    else:
        run(check_open_settlement_orders(client, CID))
    assert client.get_page.call_args.kwargs["expand"] == "state"


def test_existing_order_is_excluded_from_its_own_payment():
    client = SimpleNamespace(entity_href=lambda *args: "https://example.test/agent",
        get_page=AsyncMock(return_value={"rows": [{"id": str(OID), "sum": 10000}]}))
    run(check_open_settlement_orders(client, CID, exclude_order_id=OID))


@pytest.mark.parametrize("iso,code,ok", [("RUB", "643", True), ("USD", "840", False),
    ("B.RUB", "643", False), (None, None, False)])
def test_currency_check_only_reads(iso, code, ok):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json={"id": str(CURRENCY), "isoCode": iso, "code": code})
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://example.test") as http:
            client = SimpleNamespace(client=AsyncMock(return_value=http))
            return await verify_ruble_currency(client, documents()[0])
    if ok:
        assert run(check()) == CURRENCY
    else:
        with pytest.raises(ValueError):
            run(check())
    assert len(requests) == 1


def setup_confirmation(monkeypatch, *, cash="8532.10", shown=1000):
    remote, invoice = documents("9532.10", cash, shown)
    remote["invoicesOut"] = [ref(IID)]
    client = SimpleNamespace(get_customer_order=AsyncMock(return_value=remote),
        get_invoiceout=AsyncMock(return_value=invoice))
    order = SimpleNamespace(id=42, user_id=48, payment_invoice_id=None, is_paid=False,
        is_canceled=False, payment_status="created", moysklad_customerorder_id=OID,
        moysklad_invoiceout_id=None, grand_total=Decimal("8532.10"), delivery_total=Decimal("352.10"),
        checkout_snapshot={"settlement_payment": {"version": 1, "counterparty_id": str(CID),
            "organization_id": str(ORG), "gross_rubles": "9532.10", "maximum_balance_rubles": "1000.00",
            "status": "awaiting_invoice"},
            "benefits": {"bonus_applied_rubles": 1000, "stacked_discount_amount": 1000,
                "applications": [{"source_kind": SOURCE_KIND}]}})
    application = SimpleNamespace(status="pending", calculation_snapshot={})
    session = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(moysklad_counterparty_id=CID)),
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one=lambda: application)), commit=AsyncMock())
    monkeypatch.setattr(service, "ensure_no_pending_balance_order", AsyncMock())
    monkeypatch.setattr(service, "check_open_settlement_orders", AsyncMock())
    monkeypatch.setattr(service, "verify_ruble_currency", AsyncMock(return_value=CURRENCY))
    monkeypatch.setattr(moysklad_bonus, "get_moysklad_settlement_wallet", AsyncMock(
        return_value=SimpleNamespace(balance_rubles=Decimal("1000"))))
    return session, order, application, client


def test_confirmation_persists_exact_invoice_and_rounded_label(monkeypatch):
    session, order, application, client = setup_confirmation(monkeypatch, cash="8532.72")
    run(service.confirm_settlement_invoice(session, order=order, client=client))
    assert order.grand_total == Decimal("8532.72")
    assert application.discount_amount == Decimal("999.38")
    assert application.benefit_units == 1000
    assert application.external_reference == str(IID)
    assert order.checkout_snapshot["settlement_payment"]["balance_rubles"] == "999.38"
    session.commit.assert_awaited_once()


@pytest.mark.parametrize("case", ["no_invoice", "multiple", "no_balance", "zero_spent", "wrong_customer", "shipped"])
def test_failed_reconciliation_does_not_change_db(monkeypatch, case):
    session, order, application, client = setup_confirmation(monkeypatch)
    remote, invoice = client.get_customer_order.return_value, client.get_invoiceout.return_value
    original = deepcopy(order.checkout_snapshot)
    if case == "no_invoice": remote["invoicesOut"] = []
    if case == "multiple": remote["invoicesOut"] *= 2
    if case == "no_balance": moysklad_bonus.get_moysklad_settlement_wallet.return_value.balance_rubles = Decimal("0")
    if case == "zero_spent":
        invoice["sum"] = remote["sum"]
        invoice["attributes"][1]["value"] = 0
        remote["attributes"][0]["value"] = 0
    if case == "wrong_customer": session.get.return_value.moysklad_counterparty_id = OID
    if case == "shipped": remote["shippedSum"] = 100
    with pytest.raises((ValueError, HTTPException, SettlementNotReady)):
        run(service.confirm_settlement_invoice(session, order=order, client=client))
    session.commit.assert_not_awaited()
    assert order.checkout_snapshot == original
    assert application.status == "pending"


def test_paid_orders_do_not_recalculate_balance(monkeypatch):
    session, order, application, client = setup_confirmation(monkeypatch)
    order.is_paid = True
    order.checkout_snapshot["settlement_payment"]["status"] = "confirmed"
    run(service.confirm_settlement_invoice(session, order=order, client=client))
    client.get_customer_order.assert_not_awaited()
    session.commit.assert_not_awaited()
