"""Incoming payments for app rewards, using the company's accounting template."""

from copy import deepcopy
from decimal import Decimal
from uuid import UUID

from config import MOY_SKLAD_BONUS_PAYMENT_TEMPLATE_ID
from src.integrations.moysklad.client import MoySkladClient, entity_ref, moysklad_money
from src.integrations.moysklad.idempotency import build_sync_id
from src.normalize import coerce_uuid


def _href(value):
    return (value.get("meta") or {}).get("href") if isinstance(value, dict) else None


async def create_bonus_balance_payment(
    client: MoySkladClient, *, counterparty_id: UUID, amount: Decimal,
    external_code: str, description: str, payment_purpose: str,
    is_welcome: bool = False,
) -> dict:
    if not Decimal(amount).is_finite() or Decimal(amount) <= 0:
        raise ValueError("Bonus incoming payment amount must be positive")
    amount_minor = moysklad_money(amount)
    if amount_minor <= 0:
        raise ValueError("Bonus incoming payment amount must be positive")
    existing = await client._find_entity_by_external_code("paymentin", external_code)
    template_id = coerce_uuid(MOY_SKLAD_BONUS_PAYMENT_TEMPLATE_ID)
    if template_id is None:
        raise RuntimeError("Bonus incoming payment template is not configured")
    template = await client._get_entity_by_id("paymentin", template_id)
    if template is None or template.get("applicable") is not True:
        raise RuntimeError("Bonus incoming payment template is unavailable")
    http = await client.client()
    state_href = _href(template.get("state")) or ""
    currency_ref = (template.get("rate") or {}).get("currency")
    currency_href = _href(currency_ref) or ""
    for href, prefix in [(state_href, "/entity/paymentin/metadata/states/"), (currency_href, "/entity/currency/")]:
        if not href.startswith(client.base_url + prefix) or coerce_uuid(href.rsplit("/", 1)[-1]) is None:
            raise RuntimeError("Bonus incoming payment template has an invalid accounting reference")
    state_response = await http.get(state_href)
    state_response.raise_for_status()
    currency_response = await http.get(currency_href)
    currency_response.raise_for_status()
    state = state_response.json()
    currency = currency_response.json()
    if state.get("name") != "Бонусная (Накопительная)":
        raise RuntimeError("Bonus incoming payment template has the wrong state")
    if currency.get("isoCode") != "B.RUB" or Decimal(str(currency.get("rate", 0))) != 1 or currency.get("multiplicity") != 1:
        raise RuntimeError("Bonus incoming payment template has an unsupported currency")
    payment_type = next((a for a in template.get("attributes", []) if a.get("name") == "Тип платежа"), None)
    if payment_type is None or (payment_type.get("value") or {}).get("name") != "Бонусная":
        raise RuntimeError("Bonus incoming payment template has the wrong payment type")
    attributes = [{"meta": deepcopy(payment_type["meta"]), "value": entity_ref(payment_type["value"])}]
    bonus_count = next((a for a in template.get("attributes", []) if a.get("name") == "Бонусов начислено"), None)
    if bonus_count is not None:
        if Decimal(amount) != Decimal(amount).to_integral_value():
            raise ValueError("Bonus incoming payment requires an integral reward amount")
        attributes.append({"meta": deepcopy(bonus_count["meta"]), "value": int(amount)})
    payload = {
        "externalCode": external_code,
        "syncId": str(build_sync_id(scope="loyalty-paymentin", key=external_code)),
        "applicable": True,
        "agent": client._meta_payload(href=client.entity_href("counterparty", counterparty_id), entity_type="counterparty"),
        "organization": entity_ref(template["organization"]),
        "state": entity_ref(template["state"]),
        "rate": {"currency": entity_ref(currency_ref)},
        "sum": amount_minor,
        "vatSum": 0,
        "description": description,
        "paymentPurpose": payment_purpose,
        "attributes": attributes,
    }

    def validate(payment, *, require_external_code=True):
        if (coerce_uuid(payment.get("id")) is None or payment.get("applicable") is not True
            or (require_external_code and payment.get("externalCode") != external_code)
            or Decimal(str(payment.get("sum", 0))) != amount_minor
            or Decimal(str(payment.get("vatSum", -1))) != 0
            or _href(payment.get("agent")) != _href(payload["agent"])
            or _href(payment.get("organization")) != _href(payload["organization"])
            or _href(payment.get("state")) != _href(payload["state"])
            or _href((payment.get("rate") or {}).get("currency")) != _href(currency_ref)
            or payment.get("operations")):
            raise RuntimeError("Existing bonus incoming payment does not match the requested credit")
        actual_type = next((a for a in payment.get("attributes", []) if _href(a) == _href(payment_type)), {})
        if _href(actual_type.get("value")) != _href(payment_type.get("value")):
            raise RuntimeError("Bonus incoming payment has a conflicting payment type")
        return payment

    if existing is not None:
        return validate(existing)
    if is_welcome:
        previous = await client.get_all("/entity/paymentin", filter=f"agent={client.entity_href('counterparty', counterparty_id)}")
        candidates = []
        for payment in previous:
            text = f"{payment.get('description') or ''} {payment.get('paymentPurpose') or ''}".casefold()
            if (payment.get("applicable") is True
                and any(word in text for word in ("приветств", "регистрац", "welcome"))):
                candidates.append(payment)
        if candidates:
            if len(candidates) != 1:
                raise RuntimeError("Multiple previous welcome payments require reconciliation")
            # Reuse the posted accounting document; changing its external code
            # would break the integration which originally created it.
            return validate(candidates[0], require_external_code=False)
    try:
        payment = await client._create_entity("paymentin", payload)
    except Exception:
        payment = await client._find_entity_by_external_code("paymentin", external_code)
        if payment is None:
            raise
    return validate(payment)
