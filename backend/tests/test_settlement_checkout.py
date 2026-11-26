from copy import deepcopy
from decimal import Decimal
from uuid import UUID

import pytest

from src.integrations.moysklad.settlement_checkout import (
    INVOICE_PROCESSED_ATTRIBUTE, INVOICE_SPENT_ATTRIBUTE, ORDER_SPENT_ATTRIBUTE,
    SettlementNotReady, display_spent_rubles, validate_settlement_invoice,
)

OID, IID, CID, ORG, CURRENCY = [UUID(int=n) for n in range(1, 6)]


def ref(value):
    return {"meta": {"href": f"https://example.test/entity/type/{value}"}}


def documents(gross="8257.62", cash="8008.24", displayed=250):
    common = {"applicable": True, "agent": ref(CID), "organization": ref(ORG),
              "rate": {"currency": ref(CURRENCY)}}
    order = {**deepcopy(common), "id": str(OID), "sum": float(Decimal(gross) * 100),
             "attributes": [{"id": ORDER_SPENT_ATTRIBUTE, "value": displayed}]}
    invoice = {**deepcopy(common), "id": str(IID), "customerOrder": ref(OID),
               "sum": float(Decimal(cash) * 100), "payedSum": 0,
               "attributes": [{"id": INVOICE_PROCESSED_ATTRIBUTE, "value": True},
                              {"id": INVOICE_SPENT_ATTRIBUTE, "value": displayed}]}
    return order, invoice


def validate(order, invoice, *, maximum_balance_rubles=Decimal("1000"), **kwargs):
    return validate_settlement_invoice(order, invoice, order_id=OID, counterparty_id=CID,
        organization_id=ORG, currency_id=CURRENCY, gross_rubles=Decimal(str(order["sum"])) / 100,
        maximum_balance_rubles=maximum_balance_rubles, **kwargs)


@pytest.mark.parametrize("value,expected", [("0", 0), ("0.01", 1), ("249.38", 250),
    ("207.81", 208), ("250", 250), ("250.01", 251)])
def test_only_displayed_bonus_amount_is_rounded_up(value, expected):
    assert display_spent_rubles(value) == expected


@pytest.mark.parametrize("gross,cash,shown,actual", [
    ("8257.62", "8008.24", 250, "249.38"),
    ("4537.62", "4329.81", 208, "207.81"),
    ("9532.10", "8532.10", 1000, "1000.00"),
])
def test_payment_uses_exact_invoice_not_rounded_bonus_field(gross, cash, shown, actual):
    result = validate(*documents(gross, cash, shown))
    assert result.cash_rubles == Decimal(cash)
    assert result.balance_rubles == Decimal(actual)
    assert result.displayed_spent_rubles == shown
    assert result.cash_rubles + result.balance_rubles == Decimal(gross)


@pytest.mark.parametrize("value", [None, True, "NaN", "Infinity", "-0.01", "0.001"])
def test_invalid_amounts_are_not_silently_rounded(value):
    with pytest.raises(ValueError):
        display_spent_rubles(value)


@pytest.mark.parametrize("field,value", [("agent", ref(UUID(int=99))),
    ("organization", ref(UUID(int=99))), ("customerOrder", ref(UUID(int=99))),
    ("applicable", False), ("deleted", "2026-10-15"), ("payedSum", 1),
    ("sum", 900000)])
def test_wrong_or_already_paid_invoice_is_rejected(field, value):
    order, invoice = documents()
    invoice[field] = value
    with pytest.raises(ValueError):
        validate(order, invoice)


def test_wait_for_robot_instead_of_creating_another_invoice():
    order, invoice = documents()
    invoice["attributes"][0]["value"] = False
    with pytest.raises(SettlementNotReady):
        validate(order, invoice)


def test_display_field_does_not_authorize_overspending():
    order, invoice = documents("2000", "999", 1001)
    with pytest.raises(ValueError, match="available balance"):
        validate(order, invoice)


@pytest.mark.parametrize("label", [True, "250", 250.1, None, 249])
def test_spending_label_must_be_an_integer_ceiling(label):
    order, invoice = documents()
    invoice["attributes"][1]["value"] = label
    with pytest.raises(ValueError):
        validate(order, invoice)


def test_zero_cash_and_full_balance_are_valid():
    result = validate(*documents("1000", "0", 1000))
    assert result.cash_rubles == 0
    assert result.balance_rubles == 1000


def test_automatic_zero_balance_accepts_omitted_order_label_after_robot_finishes():
    order, invoice = documents("5842.10", "5842.10", 0)
    order["attributes"] = []
    result = validate(order, invoice, maximum_balance_rubles=0, automatic_balance=True)
    assert result.cash_rubles == Decimal("5842.10")
    assert result.balance_rubles == result.displayed_spent_rubles == 0


@pytest.mark.parametrize("auto,maximum,requested,cash,label", [
    (True, 1, None, "5842.10", 0), (True, 1, None, "5841.10", 1),
    (False, 0, None, "5842.10", 0), (True, 0, 0, "5842.10", 0),
])
def test_other_checkouts_still_require_order_label(auto, maximum, requested, cash, label):
    order, invoice = documents("5842.10", cash, label)
    order["attributes"] = []
    with pytest.raises(SettlementNotReady):
        validate(order, invoice, maximum_balance_rubles=maximum, automatic_balance=auto,
                 requested_balance_rubles=requested)


@pytest.mark.parametrize("value", [None, False, "0", 1])
def test_present_invalid_order_label_is_not_omitted_zero(value):
    order, invoice = documents("5842.10", "5842.10", 0)
    order["attributes"][0]["value"] = value
    with pytest.raises(SettlementNotReady):
        validate(order, invoice, maximum_balance_rubles=0, automatic_balance=True)


@pytest.mark.parametrize("missing,exc", [(INVOICE_PROCESSED_ATTRIBUTE, SettlementNotReady),
                                        (INVOICE_SPENT_ATTRIBUTE, ValueError)])
def test_automatic_zero_balance_requires_processed_invoice_with_zero_label(missing, exc):
    order, invoice = documents("5842.10", "5842.10", 0)
    order["attributes"] = []
    invoice["attributes"] = [a for a in invoice["attributes"] if a["id"] != missing]
    with pytest.raises(exc):
        validate(order, invoice, maximum_balance_rubles=0, automatic_balance=True)


def test_current_robots_rounding_uses_exact_cash_and_preserves_legacy_label():
    order, invoice = documents("46160", "42074.85", 4087)
    result = validate_settlement_invoice(order, invoice, order_id=OID, counterparty_id=CID,
        organization_id=ORG, currency_id=CURRENCY, gross_rubles=Decimal("46160"),
        maximum_balance_rubles=Decimal("4087"), automatic_balance=True, position_count=12)
    assert result.cash_rubles == Decimal("42074.85")
    assert result.balance_rubles == Decimal("4085.15")
    assert result.displayed_spent_rubles == 4087


@pytest.mark.parametrize("cash,label", [("42074.85", 4100), ("42000", 4087), ("44000", 4087)])
def test_automatic_mode_does_not_accept_unexplained_amounts(cash, label):
    with pytest.raises(ValueError):
        validate_settlement_invoice(*documents("46160", cash, label), order_id=OID,
            counterparty_id=CID, organization_id=ORG, currency_id=CURRENCY,
            gross_rubles=Decimal("46160"), maximum_balance_rubles=Decimal("4087"),
            automatic_balance=True, position_count=12)


@pytest.mark.parametrize("field,value", [("rate", {"currency": ref(UUID(int=99))}),
    ("rate", {"currency": ref(CURRENCY), "value": 2}),
    ("state", {"stateType": "Unsuccessful"})])
def test_wrong_currency_conversion_or_canceled_document_is_rejected(field, value):
    order, invoice = documents()
    invoice[field] = value
    with pytest.raises(ValueError):
        validate(order, invoice)
