from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException

import config
from src.app.services.orders import crm, payments, settlement_payment
from src.integrations.amocrm.client import AsyncAmoCRM
from src.integrations.amocrm.constants import CF
from src.integrations.moysklad.client import MoySkladClient
from src.integrations.moysklad.client.rate_limit import PacedMoySkladClient
from src.integrations.moysklad.order_sync import attributes, contacts

OID, IID, CID, ORG = (UUID(int=i) for i in range(1, 5))


def test_provider_invoice_without_current_qr_does_not_complete_checkout(monkeypatch):
    from src.app.services.orders.checkout_readiness import checkout_preparing
    monkeypatch.setattr(config, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    snapshot = {"order_export_version": 1}
    order = SimpleNamespace(checkout_snapshot=snapshot, status="", is_paid=False, is_active=True,
        is_canceled=False, is_shipped=False, amocrm_lead_id=7, moysklad_customerorder_id=OID,
        moysklad_invoiceout_id=IID, payment_method="sbp", payment_invoice_id="new")
    assert checkout_preparing(order)
    snapshot["sbp_ready_invoice_id"] = "old"
    assert checkout_preparing(order)
    snapshot["sbp_ready_invoice_id"] = "new"
    assert not checkout_preparing(order)
    order.moysklad_customerorder_id = None
    assert checkout_preparing(order)


async def test_missing_qr_for_new_invoice_never_returns_qr_from_previous_attempt(tmp_path, monkeypatch):
    from src.app.services.orders import payment_qr_storage as storage
    monkeypatch.setattr(storage, "ORDERS_MEDIA_DIR", tmp_path)
    old = storage.build_order_payment_qr_path(7, 42, "invoice-1")
    old.parent.mkdir()
    old.touch()
    assert await storage.save_order_payment_qr(7, 42, "invoice-1", qr_image=None, qr_url=None) == old
    assert await storage.save_order_payment_qr(7, 42, "invoice-2", qr_image=None, qr_url=None) is None

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def document_rows(amount=642140):
    order = {"id": str(OID), "applicable": True, "sum": amount, "invoicesOut": [{"id": str(IID)}],
             "agent": {"id": str(CID)}, "organization": {"id": str(ORG)}}
    invoice = {"id": str(IID), "applicable": True, "sum": amount, "customerOrder": {"id": str(OID)},
               "agent": {"id": str(CID)}, "organization": {"id": str(ORG)}, "name": "Invoice 1"}
    return order, invoice


@pytest.mark.parametrize("platform,channel,payment,method,delivery,provider", [
    ("ios", 1234871, "sbp", 1233749, "CDEK", 1233181),
    ("android", 1234873, "later", 1233175, "YANDEX", 1233183),
    ("web", 1234867, "sbp", 1233749, "YANDEX", 1233183),
])
async def test_amo_fields_and_contact_are_present_when_lead_is_created(platform, channel, payment, method, delivery, provider):
    amo = AsyncAmoCRM()
    amo._post = AsyncMock(side_effect=[{"_embedded": {"leads": [{"id": 17}]}}, OSError("note unavailable")])
    order = SimpleNamespace(checkout_snapshot={"client_platform": platform, "checkout_data": {
        "items": [{"name": "Product", "feature_name": "Box", "qty": 2, "subtotal": 190}]}},
        comment="Call first", grand_total=Decimal("6421.40"), selected_delivery_service=delivery, payment_method=payment)
    lead = await amo.create_lead_with_contact_and_note(
        lead_name="Customer", price=6421, address_str="Pickup 15", phone="+79990000000", email="customer@example.com",
        order_number="EP-123", delivery_service=delivery, note_text="Note", payment_method="Legacy label",
        delivery_sum=Decimal("352.10"), contact_id=10, order_fields=crm._checkout_lead_fields(order, "Pickup 15"))
    payload = amo._post.await_args_list[0].kwargs["json"][0]
    fields = {entry["field_id"]: entry["values"][0] for entry in payload["custom_fields_values"]}
    assert lead["id"] == 17
    assert payload["_embedded"]["contacts"] == [{"id": 10}]
    assert fields[CF["sales_channel"]] == {"enum_id": channel}
    assert fields[CF["checkout_payment_method"]] == {"enum_id": method}
    assert fields[CF["delivery_method"]] == {"enum_id": provider}
    assert fields[CF["payment_status"]] == {"enum_id": 1233115}
    assert fields[CF["shipment_address"]] == {"value": "Pickup 15"}
    assert fields[CF["order_comment"]] == {"value": "Call first"}
    assert fields[CF["cash_due"]] == {"value": 6421.4}
    assert "Product (Box) 2" in fields[CF["composition"]]["value"]
    assert CF["cdek_number"] not in fields
    assert "responsible_user_id" not in payload


@pytest.mark.parametrize("platform", ["ios", "android", "web"])
async def test_standard_moysklad_channels_do_not_require_new_environment_values(monkeypatch, platform):
    monkeypatch.setattr(attributes, "MOY_SKLAD_IOS_SALES_CHANNEL_HREF", None)
    monkeypatch.setattr(attributes, "MOY_SKLAD_ANDROID_SALES_CHANNEL_HREF", None)
    monkeypatch.setattr(attributes, "MOY_SKLAD_TELEGRAM_SALES_CHANNEL_HREF", None)
    client = MoySkladClient(token="test")
    monkeypatch.setattr(client, "find_store_by_name", AsyncMock())
    monkeypatch.setattr(client, "find_customerorder_state_by_name", AsyncMock())
    refs = await attributes._resolve_customerorder_refs(client, SimpleNamespace(checkout_snapshot={
        "client_platform": platform, "order_export_version": 1}))
    assert refs["sales_channel"]["meta"]["href"].endswith(attributes._STANDARD_CHANNEL_IDS[platform])


async def test_different_receiver_stays_out_of_an_existing_buyers_contact(monkeypatch):
    user = SimpleNamespace(contact_id=12, name="Buyer", surname="Name", email="buyer@example.com", phone_number="+79990000001")
    order = SimpleNamespace(amocrm_lead_id=None, order_number="EP-123", recipient=SimpleNamespace(
        name="Recipient", surname="Other", email="other@example.com", phone="+79990000002"),
        checkout_snapshot={"contact_info": {"name": "Recipient", "surname": "Other", "email": "other@example.com"}},
        selected_delivery_payload={}, delivery_string="Office", selected_delivery_service="CDEK", payment_method="sbp",
        delivery_total=Decimal(10), grand_total=Decimal(20), comment=None, created_at=None)
    amo = AsyncAmoCRM()
    amo.get_contact = AsyncMock(return_value={"id": 12, "custom_fields_values": [
        {"field_code": "PHONE", "values": [{"value": "+79990000001"}]},
        {"field_code": "EMAIL", "values": [{"value": "buyer@example.com"}]},
    ]})
    amo.update_contact = AsyncMock()
    amo.find_lead_by_order_number = AsyncMock(return_value=None)
    amo.create_lead_with_contact_and_note = AsyncMock(return_value={"id": 17})
    monkeypatch.setattr(crm, "amocrm_client", amo)
    session = SimpleNamespace(flush=AsyncMock())
    assert await crm.ensure_order_has_amocrm_lead(session, order, user=user) == 17
    assert await crm.ensure_order_has_amocrm_lead(session, order, user=user) == 17
    amo.update_contact.assert_not_awaited()
    amo.create_lead_with_contact_and_note.assert_awaited_once()
    assert "other@example.com" in amo.create_lead_with_contact_and_note.call_args.kwargs["note_text"]
    assert contacts._counterparty_phone(user, order) == "+79990000001"
    assert contacts._counterparty_email(user, order) == "buyer@example.com"
    assert contacts._full_name(user, order) == "Buyer Name"


@pytest.mark.parametrize("case", ["robot_invoice", "manager_without_invoice", "duplicate", "different_order", "different_sum"])
async def test_linked_moysklad_invoice_is_reused_or_rejected_without_post(monkeypatch, case):
    client = MoySkladClient(token="test")
    order, invoice = document_rows()
    if case == "manager_without_invoice":
        order["invoicesOut"] = []
    if case == "duplicate":
        order["invoicesOut"].append({"id": str(UUID(int=9))})
    if case == "different_order":
        invoice["customerOrder"]["id"] = str(CID)
    if case == "different_sum":
        invoice["sum"] -= 1
    monkeypatch.setattr(client, "get_customer_order", AsyncMock(return_value=order))
    async def get_invoice(invoice_id):
        return {**invoice, "id": str(invoice_id)}
    monkeypatch.setattr(client, "get_invoiceout", get_invoice)
    monkeypatch.setattr(client, "create_invoiceout", AsyncMock())
    args = dict(external_code="app:invoice", sync_id=IID, name="App order", organization_id=ORG, counterparty_id=CID,
        positions=[{"price": 642140, "quantity": 1}], customerorder_id=OID, create_if_missing=case != "manager_without_invoice")
    if case in {"robot_invoice", "manager_without_invoice"}:
        result = await client.resolve_or_sync_invoiceout(**args)
        assert result is None if case == "manager_without_invoice" else result.invoiceout_id == IID and not result.created
    else:
        with pytest.raises(HTTPException) as error:
            await client.resolve_or_sync_invoiceout(**args)
        assert error.value.status_code == 409
    client.create_invoiceout.assert_not_awaited()


@pytest.mark.parametrize("case", ["match", "new_total", "missing_id", "second_invoice", "already_paid", "old_order",
                                  "manager_linked", "manager_not_ready", "manager_duplicate"])
async def test_only_matching_unpaid_moysklad_invoice_allows_new_sbp(monkeypatch, case):
    monkeypatch.setattr(config, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    remote, invoice = document_rows()
    currency = UUID(int=99)
    for document in (remote, invoice):
        document["rate"] = {"currency": {"id": str(currency)}, "value": 1}
    monkeypatch.setattr(settlement_payment, "verify_ruble_currency", AsyncMock(return_value=currency))
    order = SimpleNamespace(moysklad_customerorder_id=OID, moysklad_invoiceout_id=IID,
                            grand_total=Decimal("6421.40"), checkout_snapshot={"order_export_version": 1,
                                "moysklad_document_identity": {"counterparty_id": str(CID), "organization_id": str(ORG)}})
    if case == "new_total": invoice["sum"] -= 1
    if case == "missing_id": order.moysklad_invoiceout_id = None
    if case.startswith("manager_"):
        order.moysklad_invoiceout_id = None
    if case == "manager_not_ready": remote["invoicesOut"] = []
    if case == "manager_duplicate": remote["invoicesOut"].append({"id": str(UUID(int=8))})
    if case == "second_invoice": remote["invoicesOut"].append({"id": str(UUID(int=8))})
    if case == "already_paid": invoice["payedSum"] = 100
    if case == "old_order":
        order.checkout_snapshot = {}
        invoice["sum"] -= 1
    client = SimpleNamespace(get_customer_order=AsyncMock(return_value=remote), get_invoiceout=AsyncMock(return_value=invoice))
    if case.startswith("manager_"):
        if case == "manager_linked":
            assert await settlement_payment.verify_standard_sbp_invoice(order, client=client, discover_linked=True) == IID
        else:
            with pytest.raises(HTTPException) as error:
                await settlement_payment.verify_standard_sbp_invoice(order, client=client, discover_linked=True)
            assert error.value.status_code == 409
        return
    if case in ("match", "old_order"):
        await settlement_payment.verify_standard_sbp_invoice(order, client=client)
    else:
        with pytest.raises(HTTPException) as error:
            await settlement_payment.verify_standard_sbp_invoice(order, client=client)
        assert error.value.status_code == 409
    if case in ("missing_id", "old_order"):
        client.get_invoiceout.assert_not_awaited()


async def test_conflicting_sbp_invoice_blocks_the_gateway(monkeypatch):
    monkeypatch.setattr(payments, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    monkeypatch.setattr(payments, "verify_no_unapproved_balance", AsyncMock())
    verify = AsyncMock(side_effect=HTTPException(409, "Amount mismatch"))
    monkeypatch.setattr(payments, "verify_standard_sbp_invoice", verify)
    gateway = AsyncMock()
    monkeypatch.setattr(payments.intellectmoney, "create_invoice", gateway)
    order = SimpleNamespace(id=42, checkout_snapshot={"order_export_version": 1}, is_canceled=False, is_paid=False,
                            payment_status="draft", payment_provider=None, payment_method="sbp", payment_invoice_id=None)
    with pytest.raises(HTTPException, match="Amount mismatch"):
        await payments._create_payment_for_order(None, request=None, order=order)
    verify.assert_awaited_once()
    assert verify.await_args.args == (order,)
    assert verify.await_args.kwargs["documents"] is payments.verify_no_unapproved_balance.await_args.kwargs["documents"]
    gateway.assert_not_awaited()


@pytest.mark.parametrize("headers,repeat", [
    ({"X-Lognex-Retry-After": "750"}, True),
    ({"Retry-After": "60", "X-Lognex-Retry-After": "750"}, False),
])
async def test_moysklad_order_lookup_respects_rate_limit_without_creating_documents(monkeypatch, headers, repeat):
    client = MoySkladClient(token="test")
    row = {"id": str(OID), "externalCode": "app_order:22"}
    from time import monotonic
    calls = []
    def remote(request):
        assert request.method == "GET"
        calls.append(monotonic())
        return httpx.Response(429, headers=headers) if len(calls) == 1 else httpx.Response(200, json={"rows": [row]})
    async with PacedMoySkladClient(credential="test", base_url="https://example.test",
            transport=httpx.MockTransport(remote)) as http:
        monkeypatch.setattr(client, "client", AsyncMock(return_value=http))
        if repeat:
            assert await client._find_entity_by_external_code("customerorder", "app_order:22") == row
            assert len(calls) == 2 and calls[1] - calls[0] >= 0.74
        else:
            with pytest.raises(httpx.HTTPStatusError):
                await client._find_entity_by_external_code("customerorder", "app_order:22")
            assert len(calls) == 1


async def test_rate_limit_on_invoice_validation_keeps_payment_in_preparation(monkeypatch):
    monkeypatch.setattr(config, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    request = httpx.Request("GET", "https://example.test/entity/customerorder")
    response = httpx.Response(429, headers={"X-Lognex-Retry-After": "10500"}, request=request)
    lookup = AsyncMock(side_effect=httpx.HTTPStatusError("rate limit", request=request, response=response))
    order = SimpleNamespace(moysklad_customerorder_id=OID, moysklad_invoiceout_id=IID,
                            checkout_snapshot={"order_export_version": 1})
    with pytest.raises(HTTPException) as error:
        await settlement_payment.verify_standard_sbp_invoice(order, client=SimpleNamespace(get_customer_order=lookup))
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "settlement_pending"
    assert error.value.detail["retry_after_seconds"] == 11
