"""Read the settlement calculated by MoySklad without posting another payment."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any
from uuid import UUID

from src.normalize import coerce_uuid

SOURCE_KIND = "moysklad_settlement"
ORDER_SPENT_ATTRIBUTE = "bb327e7f-a095-11f1-0a80-0dbe00169bb6"
INVOICE_SPENT_ATTRIBUTE = "01d9184e-a097-11f1-0a80-104a00165c6f"
INVOICE_PROCESSED_ATTRIBUTE = "71a2d94b-9ba9-11f1-0a80-1a5d000c2a36"


def order_settlement(order) -> dict | None:
    value = (getattr(order, "checkout_snapshot", None) or {}).get("settlement_payment")
    return value if isinstance(value, dict) and value.get("version") == 1 else None


class SettlementNotReady(RuntimeError):
    pass


def money(value: Any) -> Decimal:
    try:
        if isinstance(value, bool) or value is None:
            raise ValueError("Missing monetary amount")
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result != result.quantize(Decimal("0.01")):
            raise ValueError("Invalid monetary amount")
        return result.quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError("Invalid monetary amount") from exc


def display_spent_rubles(amount: Any) -> int:
    """The integer MS field is a label, never the amount sent to the gateway."""
    return int(money(amount).to_integral_value(rounding=ROUND_CEILING))


def entity_id(value: Any) -> UUID | None:
    if not isinstance(value, dict):
        return None
    direct = coerce_uuid(value.get("id"))
    href = (value.get("meta") or {}).get("href")
    return direct or (coerce_uuid(href.rstrip("/").rsplit("/", 1)[-1]) if isinstance(href, str) else None)


def attributes(row: dict) -> dict:
    return {attr.get("id"): attr.get("value") for attr in row.get("attributes", [])}


@dataclass(frozen=True)
class SettlementInvoice:
    invoice_id: UUID
    gross_rubles: Decimal
    cash_rubles: Decimal
    balance_rubles: Decimal
    displayed_spent_rubles: int


def validate_settlement_invoice(
    order: dict,
    invoice: dict,
    *,
    order_id: UUID,
    counterparty_id: UUID,
    organization_id: UUID,
    currency_id: UUID,
    gross_rubles: Decimal,
    maximum_balance_rubles: Decimal,
) -> SettlementInvoice:
    """Validate linked documents and use their exact difference, not a rounded field."""
    if any(coerce_uuid(value) is None for value in (order_id, counterparty_id, organization_id, currency_id)):
        raise ValueError("Missing settlement identity")
    gross_rubles = money(gross_rubles)
    if entity_id(order) != order_id or entity_id(invoice.get("customerOrder")) != order_id:
        raise ValueError("Settlement invoice belongs to a different order")
    iid = entity_id(invoice)
    if iid is None:
        raise ValueError("Settlement invoice has no id")
    for row in (order, invoice):
        if row.get("deleted") or row.get("applicable") is not True:
            raise ValueError("Settlement document is not active")
        if (row.get("state") or {}).get("stateType") == "Unsuccessful":
            raise ValueError("Settlement document is canceled")
        if entity_id(row.get("agent")) != counterparty_id:
            raise ValueError("Settlement counterparty mismatch")
        if entity_id(row.get("organization")) != organization_id:
            raise ValueError("Settlement organization mismatch")
    order_currency = entity_id((order.get("rate") or {}).get("currency"))
    if order_currency != currency_id or currency_id != entity_id((invoice.get("rate") or {}).get("currency")):
        raise ValueError("Settlement currency mismatch")
    for row in (order, invoice):
        if Decimal(str((row.get("rate") or {}).get("value", 1))) != 1:
            raise ValueError("Settlement currency conversion is not supported")
    if money(order.get("sum")) / 100 != money(gross_rubles):
        raise ValueError("Settlement order amount changed")
    if money(invoice.get("payedSum", 0)) > 0:
        raise ValueError("Settlement invoice already has payments; manual reconciliation required")
    if attributes(invoice).get(INVOICE_PROCESSED_ATTRIBUTE) is not True:
        raise SettlementNotReady("MoySklad has not calculated this invoice yet")
    cash = money(invoice.get("sum")) / 100
    if cash > gross_rubles:
        raise ValueError("Settlement invoice exceeds the order amount")
    spent = money(gross_rubles - cash)
    if spent > money(maximum_balance_rubles):
        raise ValueError("Settlement exceeds the available balance")
    shown = display_spent_rubles(spent)
    label = attributes(invoice).get(INVOICE_SPENT_ATTRIBUTE)
    if isinstance(label, bool) or not isinstance(label, int) or label != shown:
        raise ValueError("Settlement invoice spending label is inconsistent")
    order_label = attributes(order).get(ORDER_SPENT_ATTRIBUTE)
    if isinstance(order_label, bool) or not isinstance(order_label, int) or order_label != shown:
        raise SettlementNotReady("MoySklad order and invoice are not synchronized yet")
    return SettlementInvoice(iid, money(gross_rubles), money(cash), spent, shown)


async def check_open_settlement_orders(client, counterparty_id, *, exclude_order_id=None):
    """Read other channels too: prepayments remain on the balance until shipment."""
    for offset in range(0, 1000, 100):
        page = await client.get_page("/entity/customerorder", offset=offset,
            filter=f"agent={client.entity_href('counterparty', counterparty_id)};applicable=true",
            expand="state")
        rows = page.get("rows")
        if not isinstance(rows, list):
            raise ValueError("Invalid MoySklad order listing")
        for row in rows:
            if entity_id(row) is None:
                raise ValueError("Invalid MoySklad order identity")
            if entity_id(row) == exclude_order_id or row.get("deleted") or row.get("applicable") is False:
                continue
            if (row.get("state") or {}).get("stateType") == "Unsuccessful":
                continue
            if money(row.get("shippedSum", 0)) >= money(row.get("sum")):
                continue
            raise SettlementNotReady("В МойСклад есть незавершённый заказ этого клиента. Чтобы не использовать баланс дважды, сначала завершите или отмените его через менеджера.")
        if not page.get("meta", {}).get("nextHref") and len(rows) < 100:
            return
    raise SettlementNotReady("Слишком много заказов для автоматической сверки баланса. Обратитесь к менеджеру.")


async def verify_ruble_currency(client, order):
    currency_id = entity_id((order.get("rate") or {}).get("currency"))
    if currency_id is None:
        raise ValueError("Settlement currency is missing")
    http = await client.client()
    response = await http.get(f"/entity/currency/{currency_id}")
    response.raise_for_status()
    currency = response.json()
    if entity_id(currency) != currency_id or currency.get("isoCode") != "RUB" or str(currency.get("code")) != "643":
        raise ValueError("Only RUB settlement is supported")
    return currency_id
