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


def test_expected_receipts_and_reserved_units_are_not_sellable():
    from src.integrations.moysklad.utils import physical_free_stock
    assert physical_free_stock({"stock": 5, "reserve": 4, "inTransit": 10, "quantity": 11}, 0) == 1
    assert physical_free_stock({"stock": 5, "reserve": 6}, 0) == 0
    assert physical_free_stock({"quantity": 100}, 0) == 0


def test_invalid_price_configuration_cannot_select_missing_references(monkeypatch):
    from src.integrations.moysklad import utils
    monkeypatch.setattr(utils, "MOY_SKLAD_PRICE_TYPE_ID", "invalid")
    monkeypatch.setattr(utils, "MOY_SKLAD_CURRENCY_ID", "invalid")
    assert utils.sale_price({"salePrices": [{"value": 10000}]}) is None


@pytest.mark.parametrize("snapshot", [
    {"discount_excluded_product_ids": [2]},
    {"priced_items": [{"variant_id": 1, "quantity": 2, "line_total": "180.00"},
                      {"variant_id": 2, "quantity": 1, "line_total": "100.00"}]},
])
def test_export_does_not_spread_personal_discount_onto_excluded_products(snapshot):
    from src.integrations.moysklad.client import MoySkladClient
    from src.integrations.moysklad.order_sync.positions import _build_customerorder_positions
    first, second = uuid4(), uuid4()
    order = SimpleNamespace(basket_subtotal=Decimal("300"), grand_total=Decimal("280"), delivery_total=Decimal("0"),
        checkout_snapshot={"benefits": snapshot}, items=[
            SimpleNamespace(variant_id=1, product_id=1, quantity=2, line_total=Decimal("200")),
            SimpleNamespace(variant_id=2, product_id=2, quantity=1, line_total=Decimal("100"))])
    positions, missing = _build_customerorder_positions(moysklad_client=MoySkladClient(token="test"),
        assortment_refs={1: ("product", first), 2: ("product", second)}, order=order)
    assert not missing
    amounts = {p["assortment"]["meta"]["href"].rsplit("/", 1)[-1]: Decimal(str(p["price"])) * p["quantity"] for p in positions}
    assert amounts[str(first)] == 18000
    assert amounts[str(second)] == 10000


@pytest.mark.parametrize("stock,reserved,valid", [(5, 2, True), (1, 2, False), (5, 1, False)])
def test_remote_reserve_is_checked_again_before_payment(stock, reserved, valid):
    import asyncio
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from src.app.services.orders.stock_reservations import verify_remote_reservation
    href = "https://example.test/product"
    order = SimpleNamespace(moysklad_customerorder_id=uuid4(), checkout_snapshot={"stock_reservation": {
        "status": "exported", "remote_quantities": {href: 2}}})
    client = SimpleNamespace(get_customer_order=AsyncMock(return_value={"applicable": True,
        "positions": {"rows": [{"assortment": {"meta": {"href": href, "type": "product"}},
            "quantity": 2, "reserve": reserved, "stock": {"quantity": stock, "reserve": 2}}]}}))
    if valid:
        asyncio.run(verify_remote_reservation(order, client=client))
    else:
        with pytest.raises(HTTPException):
            asyncio.run(verify_remote_reservation(order, client=client))

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
from test_orders_api import second_registered_user, sync_engine

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


def test_late_pending_effect_cannot_clear_a_confirmed_payment(client, registered_user, variant_factory, stub_amocrm, monkeypatch):
    from src.database import SessionLocal
    from src.database.crud import get_order_by_id
    from src.app.services.orders.crm import _move_lead_to_pending_payment
    oid, payload = prepared_payment(client, registered_user, variant_factory, monkeypatch)
    assert client.post("/api/v1/webhooks/intellectmoney", data={**payload, "PaymentStatus": "5"}).status_code == 200
    previous = _get_order(oid)
    async def late_effect():
        async with SessionLocal() as db:
            order = await get_order_by_id(db, oid)
            await _move_lead_to_pending_payment(db, order)
    client.portal.call(late_effect)
    current = _get_order(oid)
    assert current.is_paid is True and current.payment_status == "paid"
    assert current.status == previous.status

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


def test_last_units_are_reserved_once(client, registered_user, second_registered_user, variant_factory, stub_amocrm):
    from concurrent.futures import ThreadPoolExecutor
    from src.database.models import Variant
    catalog = variant_factory(stock=2, price=Decimal("100"))
    customers = [registered_user, second_registered_user]
    drafts = [_create_ready_draft(client, u["headers"], catalog["variant_id"]) for u in customers]
    def buy(index):
        return client.post("/api/v1/users/me/orders", headers=customers[index]["headers"],
            json={"draft_id": drafts[index]["id"], "payment_method": "later"})
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(buy, [0, 1]))
    assert sorted(r.status_code for r in responses) == [200, 409]
    with Session(sync_engine) as db:
        variant = db.get(Variant, catalog["variant_id"])
        assert variant.stock == 0 and variant.local_reserved == 2


@pytest.mark.parametrize("ambiguous_export", [False, True])
def test_expiry_restores_only_a_confirmed_local_reservation(client, registered_user, variant_factory, stub_amocrm, ambiguous_export):
    from datetime import datetime, timedelta, timezone
    from src.database.models import Order, Variant
    from src.app.services.orders.stock_reservations import expire_local_reservations
    catalog = variant_factory(stock=5, price=Decimal("100"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])
    result = client.post("/api/v1/users/me/orders", headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "later"})
    assert result.status_code == 200, result.text
    oid = result.json()["id"]
    with Session(sync_engine) as db:
        order = db.get(Order, oid)
        hold = {**order.checkout_snapshot["stock_reservation"],
            "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
            "remote_export_attempted": ambiguous_export}
        order.checkout_snapshot = {**order.checkout_snapshot, "stock_reservation": hold}
        db.commit()
    client.portal.call(expire_local_reservations)
    with Session(sync_engine) as db:
        variant, order = db.get(Variant, catalog["variant_id"]), db.get(Order, oid)
        assert variant.stock == (3 if ambiguous_export else 5)
        assert variant.local_reserved == (2 if ambiguous_export else 0)
        assert order.checkout_snapshot["stock_reservation"]["status"] == ("held" if ambiguous_export else "released")


@pytest.mark.parametrize("timeout_after_post", [False, True])
def test_document_export_preserves_reservation_boundary(client, registered_user, variant_factory, stub_amocrm, monkeypatch, timeout_after_post):
    from unittest.mock import AsyncMock
    from src.database import SessionLocal
    from src.database.crud import get_order_by_id
    from src.database.models import Order, Variant
    from src.integrations.moysklad.client import MoySkladClient
    from src.integrations.moysklad.order_sync import service
    from src.integrations.moysklad.schemas import MoySkladCounterpartySyncResult, MoySkladCustomerOrderSyncResult, MoySkladInvoiceOutSyncResult
    catalog = variant_factory(stock=5, price=Decimal("21"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])
    created = client.post("/api/v1/users/me/orders", headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "sbp"})
    assert created.status_code == 200, created.text
    oid = created.json()["id"]
    cid, remote_id, invoice_id, org, delivery_id = [uuid4() for _ in range(5)]
    ms = MoySkladClient(token="test", base_url="https://example.test/api")
    monkeypatch.setattr(service, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    monkeypatch.setattr(service, "get_moysklad_client", lambda: ms)
    monkeypatch.setattr(service, "_resolve_organization_id", AsyncMock(return_value=org))
    monkeypatch.setattr(service, "_resolve_customerorder_refs", AsyncMock(return_value={"store": {}, "state": {}, "sales_channel": {}}))
    monkeypatch.setattr(service, "_moysklad_custom_attr_refs", AsyncMock(return_value={"payment_method": "https://example.test/payment", "delivery_method": "https://example.test/delivery"}))
    monkeypatch.setattr(service, "_shipment_address_full", AsyncMock(return_value=None))
    monkeypatch.setattr("src.app.services.orders.crm.sync_moysklad_document_links", AsyncMock())
    monkeypatch.setattr(ms, "resolve_or_sync_counterparty", AsyncMock(return_value=MoySkladCounterpartySyncResult(cid, "test")))
    monkeypatch.setattr(ms, "get_all", AsyncMock(return_value=[{"id": str(delivery_id)}]))
    exported = {}
    async def export_order(**kwargs):
        exported.update(kwargs)
        if timeout_after_post:
            raise TimeoutError("Remote POST outcome is unknown")
        return MoySkladCustomerOrderSyncResult(remote_id, "test", created=True)
    monkeypatch.setattr(ms, "resolve_or_sync_customerorder", export_order)
    async def remote_order(*args, **kwargs):
        return {"id": str(remote_id), "sum": 24100, "applicable": True, "agent": {"id": str(cid)}, "organization": {"id": str(org)},
                "positions": {"rows": exported["positions"], "meta": {"size": len(exported["positions"])}}}
    monkeypatch.setattr(ms, "get_customer_order", remote_order)
    invoice_export = AsyncMock(return_value=MoySkladInvoiceOutSyncResult(invoice_id, "test", created=True))
    monkeypatch.setattr(ms, "resolve_or_sync_invoiceout", invoice_export)
    async def run():
        async with SessionLocal() as db:
            order = await get_order_by_id(db, oid)
            if timeout_after_post:
                with pytest.raises(TimeoutError):
                    await service.sync_order_to_moysklad(db, order=order, user=order.user)
                await db.rollback()
            else:
                result = await service.sync_order_to_moysklad(db, order=order, user=order.user)
                assert result.customerorder.customerorder_id == remote_id
    client.portal.call(run)
    with Session(sync_engine) as db:
        order, variant = db.get(Order, oid), db.get(Variant, catalog["variant_id"])
        hold = order.checkout_snapshot["stock_reservation"]
        assert hold["remote_export_attempted"] is True
        assert hold["status"] == ("held" if timeout_after_post else "exported")
        assert variant.local_reserved == (2 if timeout_after_post else 0)
        assert variant.stock == 3
        if timeout_after_post:
            invoice_export.assert_not_awaited()
        else:
            assert hold["remote_quantities"]
            assert sum(Decimal(str(p["price"])) * p["quantity"] for p in exported["positions"]) == 24100
            assert order.moysklad_invoiceout_id == invoice_id


def test_concurrent_positive_exports_only_one_takes_balance(client, registered_user, second_registered_user, variant_factory, stub_amocrm):
    import asyncio
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from sqlalchemy import select
    from src.database import SessionLocal
    from src.database.models import Order
    from src.integrations.moysklad.order_sync.service import _mark_remote_export

    cid = uuid4()
    ids = []
    for customer in (registered_user, second_registered_user):
        catalog = variant_factory(stock=5, price=Decimal("21"))
        draft = _create_ready_draft(client, customer["headers"], catalog["variant_id"])
        response = client.post("/api/v1/users/me/orders", headers=customer["headers"],
                               json={"draft_id": draft["id"], "payment_method": "sbp"})
        assert response.status_code == 200, response.text
        ids.append(response.json()["id"])
    with Session(sync_engine) as db:
        for oid in ids:
            order = db.get(Order, oid)
            order.checkout_snapshot = dict(order.checkout_snapshot, settlement_payment={
                "version": 1, "counterparty_id": str(cid), "maximum_balance_rubles": "10",
                "status": "awaiting_invoice"})
        db.commit()
    ms = SimpleNamespace(entity_href=lambda *_: "counterparty", get_page=AsyncMock(return_value={"rows": []}))
    async def race():
        async def claim(oid):
            async with SessionLocal() as db:
                order = await db.scalar(select(Order).where(Order.id == oid).with_for_update())
                try:
                    return await _mark_remote_export(db, order, cid, ms)
                except HTTPException as exc:
                    assert exc.status_code == 409 and "EP-" in exc.detail
                    return False
        result = await asyncio.gather(*(claim(oid) for oid in ids))
        assert sorted(result) == [False, True]
        # A retry after a lost remote response sees the durable claim; never claims twice.
        assert not await claim(ids[result.index(True)])
        assert not await claim(ids[result.index(False)])
    client.portal.call(race)


def test_stale_draft_requires_confirmation_of_new_price(client, registered_user, variant_factory, stub_amocrm):
    from src.database.models import Variant
    catalog = variant_factory(stock=5, price=Decimal("100"))
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])
    with Session(sync_engine) as db:
        db.get(Variant, catalog["variant_id"]).price = Decimal("120")
        db.commit()
    args = dict(headers=registered_user["headers"], json={"draft_id": draft["id"], "payment_method": "later"})
    first = client.post("/api/v1/users/me/orders", **args)
    assert first.status_code == 409 and first.json()["detail"]["code"] == "draft_repriced"
    second = client.post("/api/v1/users/me/orders", **args)
    assert second.status_code == 200
    assert Decimal(second.json()["basket_subtotal"]) == Decimal("240")


def test_archived_variant_cannot_be_purchased(client, registered_user, variant_factory, stub_amocrm):
    from src.database.models import Variant
    catalog = variant_factory(stock=5)
    draft = _create_ready_draft(client, registered_user["headers"], catalog["variant_id"])
    with Session(sync_engine) as db:
        db.get(Variant, catalog["variant_id"]).archived = True
        db.commit()
    result = client.post("/api/v1/users/me/orders", headers=registered_user["headers"],
        json={"draft_id": draft["id"], "payment_method": "later"})
    assert result.status_code == 409


def test_unit_rounding_matches_catalog_for_multiple_units(variant_factory):
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from src.app.services.benefits.service import _rounded_personal_discount
    from src.database.models import Variant
    catalog = variant_factory(stock=10, price=Decimal("0.05"))
    with Session(sync_engine) as db:
        sid = db.get(Variant, catalog["variant_id"]).system_id
    async def check():
        engine = create_async_engine(sync_engine.url.set(drivername="postgresql+asyncpg"))
        try:
            async with AsyncSession(engine) as db:
                result = await _rounded_personal_discount(db,
                    [{"variant_system_id": str(sid), "quantity": 3}], Decimal("10"), subtotal=Decimal("0.15"))
                assert result == Decimal("0.00")
        finally:
            await engine.dispose()
    asyncio.run(check())


def test_poll_does_not_mark_paid_with_wrong_invoice_amount(client, registered_user, variant_factory, stub_amocrm, monkeypatch):
    from src.app.services.orders import payments
    from unittest.mock import AsyncMock
    oid, payload = prepared_payment(client, registered_user, variant_factory, monkeypatch)
    monkeypatch.setattr(payments.intellectmoney, "get_bank_card_payment_state", AsyncMock(return_value={"Result": {"PaymentStep": "OK"}}))
    monkeypatch.setattr(payments.intellectmoney, "get_purchase_info", AsyncMock(return_value={"Result": {
        "Eshop": {"EshopId": "123"}, "Invoice": {"InvoiceId": payload["PaymentId"],
            "OrderId": payload["OrderId"], "TotalAmount": {"Amount": "0.01", "Currency": "RUB"}}}}))
    result = client.get("/api/v1/payments/status", headers=registered_user["headers"], params={"order_id": oid})
    assert result.status_code == 200 and not result.json()["is_paid"]
    assert not _get_order(oid).is_paid


def test_avatar_is_bounded_and_invalid_image_is_public_error():
    from io import BytesIO
    from PIL import Image
    from fastapi import HTTPException
    from src.app.services.avatar_storage import convert_avatar_to_png
    source = BytesIO()
    Image.new("RGB", (2048, 1024)).save(source, "PNG")
    image = Image.open(BytesIO(convert_avatar_to_png(source.getvalue())))
    assert image.size == (1024, 512)
    with pytest.raises(HTTPException) as error:
        convert_avatar_to_png(b"not an image")
    assert error.value.status_code == 400


def test_upload_stops_reading_after_limit():
    import asyncio
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from src.app.services.upload_limits import read_upload_file_limited
    upload = SimpleNamespace(read=AsyncMock(side_effect=[b"a" * 10, b"b" * 10, b"unused"]))
    with pytest.raises(HTTPException) as error:
        asyncio.run(read_upload_file_limited(upload, max_bytes=15, label="Avatar"))
    assert error.value.status_code == 413 and upload.read.await_count == 2


def test_delivery_weight_counts_all_items_and_does_not_collect_paid_delivery():
    import asyncio
    from src.app.services.orders.fulfillment_payloads import build_cdek_order_body
    from config import CDEK_PACKAGING_WEIGHT_GRAMS
    order = SimpleNamespace(checkout_snapshot={}, selected_delivery_payload={
        "deliveryMode": "office", "address": {"code": "PVZ"}},
        items=[SimpleNamespace(product_name="Product", product_sku="SKU", product_id=1,
            variant_id=2, unit_price=Decimal("99.99"), quantity=3, weight_grams=401)],
        recipient=SimpleNamespace(name="Buyer", surname="Test", phone="+79990000000", email="buyer@example.com"),
        order_number="EP-TEST", is_paid=True, delivery_total=Decimal("199.99"))
    body = asyncio.run(build_cdek_order_body(order, SimpleNamespace(tariff_codes={"office": 136}, from_location={})))
    assert body["packages"][0]["weight"] == 1203 + CDEK_PACKAGING_WEIGHT_GRAMS
    assert body["packages"][0]["items"][0]["cost"] == 99.99
    assert body["delivery_recipient_cost"]["value"] == 0


def test_catalog_snapshot_fetched_before_export_cannot_restore_reserved_stock(variant_factory):
    import asyncio
    from datetime import datetime, timedelta, timezone
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from src.database.models import Variant
    from src.integrations.moysklad.sync import upsert_catalog_rows
    from src.integrations.moysklad.schemas import MoySkladProductRow, MoySkladVariantRow
    catalog = variant_factory(stock=0, price=Decimal("100"))
    now = datetime.now(timezone.utc)
    with Session(sync_engine) as db:
        v = db.get(Variant, catalog["variant_id"])
        v.stock_valid_after = now
        p = v.product
        product_row = MoySkladProductRow(system_id=p.system_id, sku=p.sku, name=p.name, description=p.description, archived=False)
        variant_row = MoySkladVariantRow(system_id=v.system_id, product_system_id=p.system_id,
            sku=v.sku, name=v.name, stock=5, price=v.price)
        db.commit()
    async def check():
        engine = create_async_engine(sync_engine.url.set(drivername="postgresql+asyncpg"))
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await upsert_catalog_rows(db, [product_row], [variant_row], fetched_after=now - timedelta(seconds=1))
                assert (await db.get(Variant, catalog["variant_id"])).stock == 0
                await upsert_catalog_rows(db, [product_row], [variant_row], fetched_after=now + timedelta(seconds=1))
                assert (await db.get(Variant, catalog["variant_id"])).stock == 5
                await db.rollback()
        finally:
            await engine.dispose()
    asyncio.run(check())
