from collections import Counter
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, Request

from src.app.services.orders.settlement_payment import confirm_settlement_invoice
from src.integrations.moysklad.client import MoySkladClient, reference_cache
from src.integrations.moysklad.client.common import CUSTOMER_ORDER_ATTR_IDS
from src.integrations.moysklad.order_sync import attributes, common, organization, service
from src.integrations.moysklad.settlement_checkout import INVOICE_PROCESSED_ATTRIBUTE, INVOICE_SPENT_ATTRIBUTE
from test_order_amount_integrity import make_order


@pytest.mark.anyio
async def test_two_checkouts_share_only_reference_reads(monkeypatch):
    ms = MoySkladClient(base_url="https://shop-stub.test", token="test")
    upstream = FastAPI()
    reads = Counter()
    creates = []
    now = 0
    monkeypatch.setattr(reference_cache, "monotonic", lambda: now)

    def row(kind, name, **fields):
        uid = uuid4()
        return {"id": str(uid), "name": name, "meta": {"type": kind, "href": ms.entity_href(kind, uid)}, **fields}

    org = row("organization", "Test shop")
    buyer, currency, variant = uuid4(), uuid4(), uuid4()
    buyer_path = f"/entity/counterparty/{buyer}"
    currency_path = f"/entity/currency/{currency}"
    refs = {
        f"/entity/organization/{org['id']}": org,
        "/entity/store": {"rows": [row("store", common.MOY_SKLAD_REQUIRED_STORE_NAME)]},
        "/entity/service": {"rows": [row("service", "Доставка заказа")]},
        "/entity/customerorder/metadata": {"states": [row("state", common.MOY_SKLAD_STATE_NEW_ORDER)]},
        "/entity/country": {"rows": [row("country", "Russia", code="RU")]},
        currency_path: {"id": str(currency), "isoCode": "RUB", "code": "643"},
    }
    bindings = []
    for key, name in (("payment_method", common.MOY_SKLAD_PAYMENT_INTELLECT),
                      ("delivery_method", common.MOY_SKLAD_DEFAULT_DELIVERY_METHOD_NAMES["CDEK"])):
        dictionary_id = uuid4()
        bindings.append({"id": CUSTOMER_ORDER_ATTR_IDS[key],
                         "customEntityMeta": {"href": ms.entity_href("customentity", dictionary_id) + "/metadata"}})
        refs[f"/entity/customentity/{dictionary_id}"] = {"rows": [row("customentity", name)]}
    refs["/entity/customerorder/metadata/attributes"] = {"rows": bindings}
    live = {buyer_path: {"id": str(buyer)}}

    @upstream.get("/entity/{resource:path}")
    async def get(resource: str, request: Request):
        path = f"/entity/{resource}"
        reads[path] += 1
        if path == "/entity/service":
            assert request.query_params["filter"] == "name=Доставка заказа;archived=false"
        return refs[path] if path in refs else live[path]

    @upstream.post("/entity/customerorder")
    async def create(payload: dict):
        order_id = uuid4()
        positions = payload["positions"]
        remote = {**payload, "id": str(order_id), "applicable": True,
                  "sum": sum(p["price"] * p["quantity"] for p in positions),
                  "positions": {"rows": positions}, "rate": {"currency": {"id": str(currency)}}}
        creates.append(payload["externalCode"])
        live[f"/entity/customerorder/{order_id}"] = remote
        return remote

    monkeypatch.setattr(service, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    monkeypatch.setattr(service, "get_moysklad_client", lambda: ms)
    monkeypatch.setattr(organization, "MOY_SKLAD_ORGANIZATION_ID", org["id"])
    monkeypatch.setattr(organization, "MOY_SKLAD_ORGANIZATION_NAME", org["name"])
    monkeypatch.setattr(attributes, "MOY_SKLAD_IOS_SALES_CHANNEL_HREF", ms.entity_href("saleschannel", uuid4()))
    user = SimpleNamespace(id=47, moysklad_counterparty_id=buyer)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=upstream), base_url=ms.base_url) as http:
        ms._client = http
        for n, now in enumerate((0, 45 * 60), start=1):
            price, total = 100 * n, 100 * n + 20
            order = make_order([price], [1], total, 20)
            order.id, order.order_code, order.user_id = n, f"TEST-{n}", user.id
            order.is_paid = order.is_canceled = False
            order.selected_delivery_payload = {"address": {"full_address": "Moscow", "city": "Moscow", "country_code": "RU"}}
            order.checkout_snapshot.update(ms_checkout_version=2, order_export_version=1, client_platform="ios",
                benefits={"stacked_discount_amount": 0}, stock_reservation={"status": "held", "quantities": {"1": 1}},
                settlement_payment={"version": 1, "mode": "automatic", "counterparty_id": str(buyer),
                                    "gross_rubles": str(total), "maximum_balance_rubles": "0"})
            stock = SimpleNamespace(id=1, local_reserved=1)
            application = SimpleNamespace(calculation_snapshot={})
            db_result = SimpleNamespace(all=lambda: [(1, variant, None)], scalar_one=lambda: application,
                                        scalars=lambda: SimpleNamespace(all=lambda: [stock]))
            db = SimpleNamespace(execute=AsyncMock(return_value=db_result), refresh=AsyncMock(), commit=AsyncMock(),
                                 flush=AsyncMock(), get=AsyncMock(return_value=user))
            result = await service.sync_order_to_moysklad(db, order=order, user=user)
            assert result.customerorder.created and order.checkout_snapshot["stock_reservation"]["status"] == "exported"
            order_path = f"/entity/customerorder/{order.moysklad_customerorder_id}"

            # The MS robot links its invoice only after the backend read the reservation.
            remote = live[order_path]
            iid = uuid4()
            invoice_path = f"/entity/invoiceout/{iid}"
            remote["invoicesOut"] = [{"id": str(iid)}]
            live[invoice_path] = {**remote, "id": str(iid), "customerOrder": {"id": remote["id"]},
                                  "attributes": [{"id": INVOICE_PROCESSED_ATTRIBUTE, "value": True},
                                                 {"id": INVOICE_SPENT_ATTRIBUTE, "value": 0}]}
            assert await confirm_settlement_invoice(db, order=order, client=ms)
            assert order.moysklad_invoiceout_id == iid and order.grand_total == Decimal(total)
            assert reads[order_path] == 2 and reads[invoice_path] == 1

    assert len(creates) == len(set(creates)) == 2
    assert reads[buyer_path] == 2
    assert {key: reads[key] for key in refs} == dict.fromkeys(refs, 1)
    assert "/entity/region" not in reads
