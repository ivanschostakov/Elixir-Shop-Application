from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy.orm import Session
from src.app.modules.webhooks.router import _validate_payment_event
from src.integrations.moysklad.utils import sale_price
from src.app.modules.products.helpers import ProductPriceDiscountContext, resolve_variant_price
from src.app.services.benefits.settlement import parse_settlement, PROGRAM_ATTRIBUTE_ID, DISCOUNT_ATTRIBUTE_ID

def test_price_selection_is_order_independent():
    from config import MOY_SKLAD_PRICE_TYPE_ID, MOY_SKLAD_CURRENCY_ID
    retail = {"value": 10000, "priceType": {"id": MOY_SKLAD_PRICE_TYPE_ID}, "currency": {"id": MOY_SKLAD_CURRENCY_ID}}
    other = {"value": 20000, "priceType": {"id": str(uuid4())}, "currency": {"id": str(uuid4())}}
    assert sale_price({"salePrices": [other, retail]}) == Decimal("100.00")
    assert sale_price({"salePrices": [retail, other]}) == Decimal("100.00")
    assert sale_price({"salePrices": [other]}) is None
    assert sale_price({"salePrices": [retail, retail]}) is None

def test_card_uses_sequential_discounts():
    from src.database.models import Product
    p = Product(discount_percent=Decimal("10"))
    p.products_by_category = []
    assert resolve_variant_price(Decimal("1000"), ProductPriceDiscountContext(Decimal("4")), product=p)[1] == Decimal("864.00")

@pytest.mark.parametrize("discount", ["0", "3", "20", "25"])
def test_moysklad_discount_is_not_derived_from_spending(discount):
    cid = uuid4()
    card = {"id": str(cid), "salesAmount": 0, "attributes": [
        {"id": PROGRAM_ATTRIBUTE_ID, "value": {"name": "Партнерская"}},
        {"id": DISCOUNT_ATTRIBUTE_ID, "value": {"name": discount}},
    ]}
    result = parse_settlement(card, {"counterparty": {"id": str(cid)}, "balance": 0}, expected_id=cid, now=1)
    assert result.personal_discount_percent == Decimal(discount)

@pytest.mark.parametrize("field,value", [("RecipientAmount", "0.01"), ("RecipientCurrency", "USD"), ("PaymentId", "wrong"), ("EshopId", "wrong")])
def test_payment_mismatch(field, value, monkeypatch):
    from src.app.modules.webhooks import router
    monkeypatch.setattr(router.intellectmoney, "shop_id", "123")
    order = SimpleNamespace(id=1, order_number="EP-ONE", payment_invoice_id="300", payment_provider="intellectmoney", grand_total=Decimal("399"), currency="RUB")
    payload = {"EshopId": "123", "OrderId": "EP-ONE", "PaymentId": "300", "RecipientAmount": "399", "RecipientCurrency": "RUB", "PaymentStatus": "5"}
    _validate_payment_event(order, payload)
    with pytest.raises(Exception):_validate_payment_event(order, {**payload, field: value})

# Exercise the real HTTP/DB path with isolated provider fixtures.
from test_orders_api import registered_user, variant_factory, stub_amocrm, _create_ready_draft, _get_order

def prepared_payment(client, registered_user, variant_factory, monkeypatch):
    from src.database.models import Order
    from test_orders_api import sync_engine
    from src.app.modules.webhooks import router
    catalog = variant_factory(stock=5, price=Decimal("21"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])
    response = client.post("/api/v1/users/me/orders", headers=registered_user["headers"], json={"draft_id": draft["id"], "payment_method": "sbp"})
    assert response.status_code == 200
    oid = response.json()["id"]
    with Session(sync_engine) as db:
        order = db.get(Order, oid)
        order.payment_invoice_id = "3" + uuid4().hex
        order.payment_provider = "intellectmoney"
        payload = {"EshopId": "123", "OrderId": order.order_number, "PaymentId": order.payment_invoice_id, "RecipientAmount": str(order.grand_total), "RecipientCurrency": "RUB", "PaymentStatus": "3"}
        db.commit()
    monkeypatch.setattr(router.intellectmoney, "shop_id", "123")
    monkeypatch.setattr(router.intellectmoney, "verify_webhook_hash", lambda p: True)
    return oid, payload

def test_created_paid_duplicate_and_late_created(client, registered_user, variant_factory, stub_amocrm, monkeypatch):
    oid, payload = prepared_payment(client, registered_user, variant_factory, monkeypatch)
    assert client.post("/api/v1/webhooks/intellectmoney", data=payload).status_code == 200
    paid = {**payload, "PaymentStatus": "5"}
    assert client.post("/api/v1/webhooks/intellectmoney", data=paid).status_code == 200
    assert _get_order(oid).is_paid
    assert client.post("/api/v1/webhooks/intellectmoney", data=paid).status_code == 200
    assert client.post("/api/v1/webhooks/intellectmoney", data={**payload, "PaymentData": "later"}).status_code == 200
    assert _get_order(oid).payment_status == "paid"

def test_failed_event_can_be_retried(client, registered_user, variant_factory, stub_amocrm, monkeypatch):
    from src.app.modules.webhooks import router
    oid, payload = prepared_payment(client, registered_user, variant_factory, monkeypatch)
    original = router.reconcile_sbp_payment
    from fastapi import HTTPException
    async def broken(*a, **k):raise HTTPException(503)
    monkeypatch.setattr(router, "reconcile_sbp_payment", broken)
    paid = {**payload, "PaymentStatus": "5"}
    assert client.post("/api/v1/webhooks/intellectmoney", data=paid).status_code == 503
    monkeypatch.setattr(router, "reconcile_sbp_payment", original)
    assert client.post("/api/v1/webhooks/intellectmoney", data=paid).status_code == 200
    assert _get_order(oid).is_paid

def test_refund_commits_even_when_crm_fails(client, registered_user, variant_factory, stub_amocrm, monkeypatch):
    from src.app.services.orders import crm
    oid, payload = prepared_payment(client, registered_user, variant_factory, monkeypatch)
    assert client.post("/api/v1/webhooks/intellectmoney", data={**payload, "PaymentStatus": "5"}).status_code == 200
    async def broken(*a, **k):raise RuntimeError("CRM unavailable")
    monkeypatch.setattr(crm.amocrm_client, "update_lead_status", broken)
    assert client.post("/api/v1/webhooks/intellectmoney", data={**payload, "PaymentStatus": "8"}).status_code == 200
    order = _get_order(oid)
    assert order.payment_status == "refunded" and not order.is_paid
