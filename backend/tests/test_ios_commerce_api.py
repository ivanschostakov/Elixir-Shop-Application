from decimal import Decimal
import uuid
from unittest.mock import AsyncMock

import config
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import Variant
from test_catalog_access_scope import scoped_catalog
from test_guest_checkout_api import _build_guest_order_payload, _delete_user
from test_orders_api import _build_pickup_payload, _create_ready_draft, stub_amocrm
from test_products_advanced_search_api import sync_engine


@pytest.fixture
def ios_catalog(scoped_catalog, monkeypatch):
    monkeypatch.setattr(config, "IOS_COMMERCE_ENABLED", True)
    try:
        yield scoped_catalog
    finally:
        for key in ("limited_id", "regular_id"):
            _delete_user(scoped_catalog[key])


def _variant(product_id):
    with Session(sync_engine) as db:
        return db.scalar(select(Variant.id).where(Variant.product_id == product_id))


def _headers(seed, identity):
    return {**seed.get(identity, {}), "X-App-Platform": "ios"}


@pytest.fixture
def payment_provider(monkeypatch):
    invoice = AsyncMock(return_value={"Result": {"InvoiceId": "ios-test-invoice"}})
    state = {"Result": {"PaymentStep": "Created", "Form3DS":
             '{"SbpQrCodeUrl":"https://example.test/qr","SbpQrCodeImage":"https://example.test/qr.png"}'}}
    monkeypatch.setattr("src.app.services.orders.intellectmoney.create_invoice", invoice)
    monkeypatch.setattr("src.app.services.orders.intellectmoney.sbp_payment", AsyncMock(return_value=state))
    monkeypatch.setattr("src.app.services.orders.intellectmoney.get_bank_card_payment_state", AsyncMock(return_value=state))
    monkeypatch.setattr("src.app.services.orders._resolve_payment_qr_image", AsyncMock(return_value="https://example.test/qr.png"))
    return invoice


@pytest.mark.parametrize("identity", ["guest", "limited", "regular"])
def test_ios_catalog_quote_and_hidden_products(client, ios_catalog, identity):
    s = ios_catalog
    headers = _headers(s, identity)
    response = client.get("/api/v1/products", headers=headers)
    assert response.status_code == 200, response.text
    assert {row["id"] for row in response.json()} == {s["en_product_id"], s["noise_product_id"]}
    assert client.get(f"/api/v1/products/{s['en_product_id']}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/products/{s['ru_product_id']}", headers=headers).status_code == 404
    variant_id = _variant(s["en_product_id"])
    quote = client.post("/api/v1/guest/basket/quote", headers=headers,
                        json={"items": [{"variant_id": variant_id, "quantity": 2}]})
    assert quote.status_code == 200, quote.text
    assert quote.json()["total_quantity"] == 2
    assert Decimal(quote.json()["grand_total"]) == Decimal("40.00")
    hidden = client.post("/api/v1/guest/basket/quote", headers=headers,
                         json={"items": [{"variant_id": _variant(s["ru_product_id"]), "quantity": 1}]})
    assert hidden.status_code == 404, hidden.text


@pytest.mark.parametrize("identity", ["limited", "regular"])
def test_ios_basket_add_read_update_remove(client, ios_catalog, identity):
    s = ios_catalog
    headers = _headers(s, identity)
    response = client.post("/api/v1/users/me/basket/items", headers=headers,
                           json={"variant_id": _variant(s["en_product_id"]), "quantity": 1})
    assert response.status_code == 200, response.text
    item_id = response.json()["items"][0]["id"]
    loaded = client.get("/api/v1/users/me/basket", headers=headers)
    assert loaded.status_code == 200 and loaded.json()["total_quantity"] == 1
    updated = client.patch(f"/api/v1/users/me/basket/items/{item_id}", headers=headers, json={"quantity": 2})
    assert updated.status_code == 200, updated.text
    assert Decimal(updated.json()["total_amount"]) == Decimal("40.00")
    removed = client.delete(f"/api/v1/users/me/basket/items/{item_id}", headers=headers)
    assert removed.status_code == 200 and removed.json()["items"] == []
    hidden = client.post("/api/v1/users/me/basket/items", headers=headers,
                         json={"variant_id": _variant(s["ru_product_id"]), "quantity": 1})
    assert hidden.status_code == 404, hidden.text


@pytest.mark.parametrize("identity", ["limited", "regular"])
@pytest.mark.parametrize("use_draft", [False, True])
def test_ios_purchase_from_catalog_to_sbp(client, ios_catalog, identity, use_draft, stub_amocrm, payment_provider):
    s = ios_catalog
    headers = _headers(s, identity)
    variant_id = _variant(s["en_product_id"])
    if use_draft:
        draft = _create_ready_draft(client, headers, variant_id)
        order_payload = {"draft_id": draft["id"], "payment_method": "sbp"}
    else:
        added = client.post("/api/v1/users/me/basket/items", headers=headers,
                            json={"variant_id": variant_id, "quantity": 2})
        assert added.status_code == 200, added.text
        options = client.get("/api/v1/users/me/basket/checkout/options", headers=headers)
        assert options.status_code == 200, options.text
        checkout = client.patch("/api/v1/users/me/basket/checkout", headers=headers, json={
            "new_delivery_address": _build_pickup_payload(),
            "new_recipient": {"name": "Checkout", "surname": "Test", "phone": "+79991234567", "email": "checkout@example.com"},
        })
        assert checkout.status_code == 200, checkout.text
        assert Decimal(checkout.json()["grand_total"]) == Decimal("239.00")
        order_payload = {"payment_method": "sbp"}
    order = client.post("/api/v1/users/me/orders", headers=headers, json=order_payload)
    assert order.status_code == 200, order.text
    order_id = order.json()["id"]
    assert Decimal(order.json()["grand_total"]) == Decimal("239.00")
    payment = client.post("/api/v1/payments/create", headers=headers, json={"order_id": order_id})
    assert payment.status_code == 200, payment.text
    assert payment.json()["qr_url"] == "https://example.test/qr"
    assert payment.json()["is_paid"] is False
    payment_provider.assert_awaited_once()
    status = client.get("/api/v1/payments/status", headers=headers, params={"order_id": order_id})
    assert status.status_code == 200, status.text
    assert status.json()["payment_status"] == "pending"


def test_ios_guest_checkout_to_sbp(client, ios_catalog, stub_amocrm, payment_provider, monkeypatch):
    from src.app.services import orders
    monkeypatch.setattr("src.app.services.guest_checkout.amocrm_client", orders.get_amocrm_client())
    phone = "+7999" + str(int(uuid.uuid4().hex[:8], 16) % 10000000).zfill(7)
    payload = _build_guest_order_payload(variant_id=_variant(ios_catalog["en_product_id"]),
                                         email="ios-guest@example.com", phone=phone)
    payload["payment_method"] = "sbp"
    response = client.post("/api/v1/guest/orders", headers={"X-App-Platform": "ios"}, json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    try:
        payment = client.post("/api/v1/payments/create",
                              headers={"X-App-Platform": "ios", "Authorization": "Bearer " + data["access_token"]},
                              json={"order_id": data["order"]["id"]})
        assert payment.status_code == 200, payment.text
        assert payment.json()["qr_url"] == "https://example.test/qr"
    finally:
        _delete_user(data["user"]["id"])


def test_ios_rejects_hidden_items_already_in_basket(client, ios_catalog, stub_amocrm):
    s = ios_catalog
    added = client.post("/api/v1/users/me/basket/items", headers=s["regular"],
                        json={"variant_id": _variant(s["ru_product_id"]), "quantity": 1})
    assert added.status_code == 200, added.text
    order = client.post("/api/v1/users/me/orders", headers=_headers(s, "regular"), json={"payment_method": "sbp"})
    assert order.status_code == 404, order.text


def test_commerce_does_not_enable_medical_ai(client, ios_catalog):
    for path in ("/api/v1/users/me/ai-chat", "/api/v1/users/me/companion/actions"):
        response = client.post(path, headers=_headers(ios_catalog, "regular"), json={})
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "ios_feature_unavailable"
