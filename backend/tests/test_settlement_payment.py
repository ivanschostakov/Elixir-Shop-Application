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
    INVOICE_PROCESSED_ATTRIBUTE, INVOICE_SPENT_ATTRIBUTE, ORDER_SPENT_ATTRIBUTE, SOURCE_KIND, SettlementNotReady,
    check_open_settlement_orders, verify_ruble_currency,
)


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.mark.parametrize("other,blocked", [
    ({"sum": 10000, "shippedSum": 0}, False),
    ({"sum": 10000, "shippedSum": 9999, "payedSum": 10000}, False),
    ({"sum": 10000, "shippedSum": 100, "attributes": [{"id": ORDER_SPENT_ATTRIBUTE, "value": 5}]}, True),
    ({"sum": 10000, "shippedSum": 10000}, False),
    ({"sum": 10000, "state": {"stateType": "Unsuccessful"}}, False),
    ({"sum": 10000, "applicable": False}, False),
])
def test_external_pending_orders_block_repeated_balance_use(other, blocked):
    client = SimpleNamespace(entity_href=lambda *args: "https://example.test/agent",
        get_page=AsyncMock(return_value={"rows": [{"id": str(OID), "agent": ref(CID), **other}]}))
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


@pytest.mark.parametrize("case,blocked", [
    ("legacy_cash", False), ("external_confirmed_zero", False), ("external_unknown", False),
    ("robot_running", False), ("order_spent", True), ("invoice_spent", True),
    ("requested", True), ("no_consent", False), ("lower_invoice", False), ("higher_invoice", False),
    ("missing_invoice", False), ("unavailable_invoice", False), ("multiple_invoices", False),
    ("unposted_invoice", False), ("wrong_order", False), ("wrong_agent", False), ("wrong_currency", False),
    ("app_export", True), ("app_export_zero", False),
])
def test_only_positive_debit_or_real_processing_reserves_balance(case, blocked, monkeypatch):
    from src.integrations.moysklad.client.common import CUSTOMER_ORDER_ATTR_IDS
    remote, invoice = documents("6069.30", "6069.30", 0)
    remote.update(name="14-Q01E8", invoicesOut=[ref(IID)])
    if case not in {"external_confirmed_zero", "app_export_zero"}:
        invoice["attributes"] = []
        remote["attributes"] = []
    if case == "robot_running": invoice["attributes"] = [{"id": INVOICE_PROCESSED_ATTRIBUTE, "value": False}]
    if case == "order_spent": remote["attributes"] = [{"id": ORDER_SPENT_ATTRIBUTE, "value": 5}]
    if case == "invoice_spent": invoice["attributes"] = [{"id": INVOICE_SPENT_ATTRIBUTE, "value": 5}]
    if case in {"requested", "no_consent"}:
        monkeypatch.setitem(CUSTOMER_ORDER_ATTR_IDS, "balance_amount_kopecks", "requested")
        monkeypatch.setitem(CUSTOMER_ORDER_ATTR_IDS, "balance_consent", "consent")
        remote["attributes"] = [{"id": "requested", "value": 1}, {"id":"consent","value":case == "requested"}]
    if case == "lower_invoice": invoice["sum"] -= 1
    if case == "higher_invoice": invoice["sum"] += 1
    if case == "missing_invoice": remote["invoicesOut"] = []
    if case == "unavailable_invoice": invoice = None
    if case == "multiple_invoices": remote["invoicesOut"] *= 2
    if case == "unposted_invoice": invoice["applicable"] = False
    if case == "wrong_order": invoice["customerOrder"] = ref(ORG)
    if case == "wrong_agent": invoice["agent"] = ref(ORG)
    if case == "wrong_currency": invoice["rate"]["currency"] = ref(ORG)
    client = SimpleNamespace(entity_href=lambda *args: "agent", get_page=AsyncMock(return_value={"rows": [remote]}),
                             get_invoiceout=AsyncMock(return_value=invoice))
    check = check_open_settlement_orders(client, CID, processing_ids={OID} if case.startswith("app_export") else set())
    if blocked:
        with pytest.raises(SettlementNotReady, match="14-Q01E8"):
            run(check)
    else:
        run(check)


@pytest.mark.parametrize("snapshot,canceled,blocked,known", [
    ({"benefits": {"use_bonus_rubles": False, "bonus_applied_rubles": "0.00"}}, True, False, False),
    ({"benefits": {"use_bonus_rubles": False}}, True, False, False),
    ({"benefits": {"use_bonus_rubles": False, "bonus_applied_rubles": False}}, True, False, False),
    ({"settlement_payment": {"status": "awaiting_invoice", "maximum_balance_rubles": 0}}, False, False, False),
    ({"settlement_payment": {"status": "awaiting_invoice", "maximum_balance_rubles": 100}}, False, False, True),
    ({"settlement_payment": {"status": "confirmed", "balance_rubles": "0.00", "displayed_spent_rubles": 0}}, False, False, False),
    ({"settlement_payment": {"status": "confirmed", "balance_rubles": "0.01", "displayed_spent_rubles": 1}}, False, True, False),
    ({"settlement_payment": {"status": "confirmed", "balance_rubles": "0.00", "displayed_spent_rubles": 1}}, False, True, False),
    ({"settlement_payment": {"status": "awaiting_invoice"}}, True, False, False),
])
def test_local_evidence_for_remote_order(snapshot, canceled, blocked, known):
    result = SimpleNamespace(all=lambda: [(OID, "EP-test", canceled, snapshot.get("settlement_payment"), snapshot.get("benefits"))])
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    check = service.ensure_no_pending_balance_order(session, counterparty_id=CID)
    if blocked:
        with pytest.raises(HTTPException, match="EP-test"):
            run(check)
    else:
        assert run(check) == ({OID} if known else set())


@pytest.mark.parametrize("attempted,amount,blocked", [(False, 100, False), (True, 0, False), (True, 100, True)])
def test_unexported_order_only_holds_funds_after_positive_handoff(attempted, amount, blocked):
    row = (None, "EP-test", False, {"status":"awaiting_invoice","maximum_balance_rubles":amount, "export_started":attempted}, {})
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [row])))
    if blocked:
        with pytest.raises(HTTPException, match="EP-test"):
            run(service.ensure_no_pending_balance_order(session, counterparty_id=CID))
    else:
        assert run(service.ensure_no_pending_balance_order(session, counterparty_id=CID)) == set()


def test_zero_checkout_never_reads_other_orders():
    session, client = SimpleNamespace(execute=AsyncMock()), SimpleNamespace(get_page=AsyncMock())
    run(service.check_balance_use(session, counterparty_id=CID, amount="0.00", client=client))
    session.execute.assert_not_awaited()
    client.get_page.assert_not_awaited()


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


def test_zero_spend_validates_current_invoice_without_checking_old_orders(monkeypatch):
    session, order, _, client = setup_confirmation(monkeypatch, cash="9532.10", shown=0)
    order.checkout_snapshot["settlement_payment"].update(mode="automatic", maximum_balance_rubles="0")
    run(service.confirm_settlement_invoice(session, order=order, client=client))
    client.get_invoiceout.assert_awaited_once_with(IID)
    service.ensure_no_pending_balance_order.assert_not_awaited()
    service.check_open_settlement_orders.assert_not_awaited()
    moysklad_bonus.get_moysklad_settlement_wallet.assert_not_awaited()
    assert order.grand_total == Decimal("9532.10")


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


@pytest.mark.parametrize("consent,source,cash,active,blocked", [
    (False, "order", 618000, True, True),
    (False, "invoice", 618000, True, True),
    (False, None, 518008, True, True),
    (False, None, 518008, False, False),
    (False, None, 618000, True, False),
    (True, "order", 518008, True, False),
    (None, "order", 518008, True, False),
])
def test_payment_checks_for_unapproved_balance(monkeypatch, consent, source, cash, active, blocked):
    monkeypatch.setattr("config.LOYALTY_USE_SETTLEMENT_BALANCE", True)
    order = SimpleNamespace(id=42, moysklad_customerorder_id=OID, moysklad_invoiceout_id=None,
        checkout_snapshot={"benefits": {"use_bonus_rubles": consent}})
    remote = {"id": str(OID), "sum": 618000, "invoicesOut": [ref(IID)], "attributes": [
        {"id": ORDER_SPENT_ATTRIBUTE, "value": 1000 if source == "order" else 0}]}
    invoice = {"id": str(IID), "sum": cash, "applicable": active, "attributes": [
        {"id": INVOICE_SPENT_ATTRIBUTE, "value": 1000 if source == "invoice" else 0}]}
    client = SimpleNamespace(get_customer_order=AsyncMock(return_value=remote),
        get_invoiceout=AsyncMock(return_value=invoice))
    if blocked:
        with pytest.raises(HTTPException) as error:
            run(service.verify_no_unapproved_balance(order, client=client))
        assert error.value.status_code == 409
    else:
        run(service.verify_no_unapproved_balance(order, client=client))
    if consent is not False:
        client.get_customer_order.assert_not_awaited()
