import asyncio
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import create_async_engine

import config
from src.database.models import Order, OrderDraft, User
from src.app.services.benefits import service as benefits, moysklad_bonus
from src.app.services.orders import creation, settlement_payment, crm
from src.integrations.moysklad.settlement_checkout import display_spent_rubles
from test_settlement_checkout import CID, CURRENCY, IID, OID, ORG, documents, ref
from test_orders_api import (
    registered_user, variant_factory, stub_amocrm, sync_engine,
    _create_ready_draft, _get_order, _update_order,
)


@pytest.mark.parametrize("scenario", ["exact", "rounded", "full", "full_exact_balance", "partial_delivery", "wrong_invoice",
    "balance_changed", "not_ready", "cancelled", "retry", "ambiguous_gateway", "other_open_order", "zero_balance", "opt_out", "partial_request",
    "legacy_cash_order"])
def test_balance_checkout_api_uses_only_mocked_external_services(
    client, registered_user, variant_factory, stub_amocrm, monkeypatch, scenario,
):
    monkeypatch.setattr(config, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    monkeypatch.setattr(config, "LOYALTY_SETTLEMENT_CHECKOUT_ENABLED", True)
    monkeypatch.setattr(config, "MOY_SKLAD_BALANCE_CONSENT_ATTRIBUTE_ID", str(CID))
    monkeypatch.setattr(config, "MOY_SKLAD_BALANCE_AMOUNT_ATTRIBUTE_ID", str(IID))
    from src.app.services.benefits import settlement
    from src.app.services.benefits.settlement_schemas import SettlementRead
    monkeypatch.setattr(settlement, "get_account_settlement", AsyncMock(return_value=SettlementRead(
        status="fresh", loyalty_program=1, personal_discount_percent=Decimal("0"),
        balance_rubles=Decimal("1000"), total_purchases_rubles=Decimal("0"))))
    monkeypatch.setattr("src.app.services.orders.payments.MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    monkeypatch.setattr(config, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    monkeypatch.setattr(crm.amocrm_client, "update_lead_price", AsyncMock(), raising=False)
    crm_fields = AsyncMock()
    monkeypatch.setattr(crm.amocrm_client, "update_lead_order_fields", crm_fields, raising=False)
    monkeypatch.setattr(crm.amocrm_client, "add_lead_note", AsyncMock(), raising=False)
    balance = Decimal("0") if scenario == "zero_balance" else Decimal("300") if scenario == "partial_delivery" else Decimal("399") if scenario == "full_exact_balance" else Decimal("1000")
    wallet = moysklad_bonus.MoySkladBonusWallet(is_loaded=True, is_settlement=True,
        counterparty_id=CID, program_name="Balance", balance_points=int(balance),
        balance_rubles=balance, max_paid_rate_percent=Decimal("100"))
    monkeypatch.setattr(benefits, "get_user_moysklad_bonus_wallet", AsyncMock(return_value=wallet))
    monkeypatch.setattr(moysklad_bonus, "get_moysklad_settlement_wallet", AsyncMock(return_value=wallet))
    with Session(sync_engine) as db:
        user = db.get(User, registered_user["user_id"])
        user.moysklad_counterparty_id = CID
        db.commit()
    price = Decimal("100") if scenario in {"full", "full_exact_balance", "partial_delivery"} else Decimal("4590")
    gross = price * 2 + Decimal("199")
    applied = Decimal("999.38") if scenario == "rounded" else min(gross, balance)
    cash = gross - applied
    remote, invoice = documents(str(gross), str(cash), display_spent_rubles(applied))
    if scenario == "zero_balance":
        remote["attributes"] = []
    remote["invoicesOut"] = [ref(IID)]
    stock_href = "https://example.test/product"
    delivery_href = "https://example.test/delivery"
    remote["positions"] = {"rows": [
        {"assortment": {"meta": {"href": stock_href, "type": "product"}}, "quantity": 2,
         "reserve": 2, "stock": {"quantity": 10, "reserve": 2}},
        {"assortment": {"meta": {"href": delivery_href, "type": "service"}}, "quantity": 1}],
        "meta": {"size": 2}}
    ms = SimpleNamespace(
        entity_href=lambda *args: "https://example.test/agent",
        get_page=AsyncMock(return_value={"rows": []}),
        get_customer_order=AsyncMock(return_value=remote), get_invoiceout=AsyncMock(return_value=invoice),
    )
    monkeypatch.setattr(settlement_payment, "get_moysklad_client", lambda: ms)
    monkeypatch.setattr("src.integrations.moysklad.client.get_moysklad_client", lambda: ms)
    monkeypatch.setattr(settlement_payment, "verify_ruble_currency", AsyncMock(return_value=CURRENCY))
    monkeypatch.setattr(settlement_payment.asyncio, "sleep", AsyncMock())

    async def sync_mock(db, *, order, user):
        # Persistence is real; MoySklad documents and gateway calls are fixtures only.
        snapshot = deepcopy(order.checkout_snapshot)
        snapshot["settlement_payment"]["organization_id"] = str(ORG)
        snapshot["stock_reservation"]["status"] = "exported"
        snapshot["stock_reservation"]["remote_quantities"] = {stock_href: 2, delivery_href: 1}
        order.checkout_snapshot = snapshot
        order.moysklad_customerorder_id = OID
        await db.commit()
    _patched_value_65 = sync_mock
    for target in ('src.app.services.orders.creation.basket.sync_order_to_moysklad_safe', 'src.app.services.orders.creation.draft.sync_order_to_moysklad_safe',):
        monkeypatch.setattr(target, _patched_value_65)
    monkeypatch.setattr('src.app.services.orders.creation.delivery._enrich_selected_delivery_address_payload', AsyncMock())
    gateway = AsyncMock(return_value={"Result": {"InvoiceId": "mock-invoice-1"}})
    state = {"Result": {"PaymentStep": "Created", "Form3DS": '{"SbpQrCodeUrl":"https://example.test/qr"}'}}
    monkeypatch.setattr("src.app.services.orders.intellectmoney.create_invoice", gateway)
    monkeypatch.setattr("src.app.services.orders.intellectmoney.sbp_payment", AsyncMock(return_value=state))
    monkeypatch.setattr("src.app.services.orders.intellectmoney.get_bank_card_payment_state", AsyncMock(return_value=state))
    monkeypatch.setattr("src.app.services.orders._resolve_payment_qr_image", AsyncMock(return_value=None))
    catalog = variant_factory(price=price)
    headers = registered_user["headers"]
    draft = _create_ready_draft(client, headers, catalog["variant_id"])
    if scenario == "legacy_cash_order":
        old_id, old_iid = uuid4(), uuid4()
        old, old_invoice = documents("6069.30", "6069.30", 0)
        old.update(id=str(old_id), attributes=[], invoicesOut=[ref(old_iid)])
        old_invoice.update(id=str(old_iid), customerOrder=ref(old_id), attributes=[])
        ms.get_page.return_value = {"rows": [old]}
        ms.get_invoiceout.side_effect = {old_iid: old_invoice, IID: invoice}.__getitem__
        with Session(sync_engine) as db:
            original = db.get(OrderDraft, draft["id"])
            db.add(Order(user_id=original.user_id, recipient_id=original.recipient_id,
                delivery_address_id=original.delivery_address_id, order_code="OLD-" + old_id.hex[:12],
                is_canceled=True, moysklad_customerorder_id=old_id,
                checkout_snapshot={"benefits": {"use_bonus_rubles": False, "bonus_applied_rubles": 0}}))
            db.commit()
    for use_balance in (False, True):
        preview = client.post("/api/v1/users/me/benefits/check", headers=headers, json={
            "draft_id": draft["id"], "use_bonus_rubles": use_balance})
        assert preview.status_code == 200, preview.text
        expected_cash = max(Decimal("0"), gross - balance)
        assert Decimal(preview.json()["cash_total"]) == expected_cash
        assert preview.json()["balance_redemption_mode"] == "automatic"
        assert preview.json()["use_bonus_rubles"] is True
        assert Decimal(preview.json()["total_after_discounts"]) >= 0
    response = client.post("/api/v1/users/me/orders", headers=headers, json={
        "draft_id": draft["id"], "payment_method": "sbp", "use_bonus_rubles": scenario != "opt_out",
        **({"bonus_rubles_to_use": "1.00"} if scenario == "partial_request" else {})})
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["grand_total"]) == max(Decimal("0"), gross - balance)
    order_id = response.json()["id"]
    assert response.json()["checkout_snapshot"]["settlement_payment"]["gross_rubles"] == str(gross.quantize(Decimal("0.01")))
    if scenario == "wrong_invoice": invoice["customerOrder"] = ref(CID)
    if scenario == "balance_changed":
        moysklad_bonus.get_moysklad_settlement_wallet.return_value = SimpleNamespace(balance_rubles=Decimal("0"))
    if scenario == "not_ready": remote["invoicesOut"] = []
    if scenario == "ambiguous_gateway": gateway.return_value = {"Result": {}}
    if scenario == "cancelled": _update_order(order_id, is_canceled=True)
    if scenario == "other_open_order":
        ms.get_page.return_value = {"rows": [{"id": str(CID), "sum": 10000, "shippedSum": 0}]}
    response = client.post("/api/v1/payments/create", headers=headers, json={"order_id": order_id})
    if scenario == "ambiguous_gateway":
        assert response.status_code >= 500, response.text
        assert _get_order(order_id).payment_invoice_id is None
        retry = client.post("/api/v1/payments/create", headers=headers, json={"order_id": order_id})
        assert retry.status_code == 409, retry.text
        gateway.assert_awaited_once()
        return
    if scenario == "not_ready":
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "settlement_pending"
        status_response = client.get("/api/v1/payments/status", headers=headers, params={"order_id": order_id})
        assert status_response.status_code == 200, status_response.text
        assert status_response.json()["awaiting_settlement"] is True
        assert _get_order(order_id).payment_invoice_id is None
        gateway.assert_not_awaited()
        remote["invoicesOut"] = [ref(IID)]
        response = client.post("/api/v1/payments/create", headers=headers, json={"order_id": order_id})
    if scenario in {"wrong_invoice", "balance_changed", "cancelled", "other_open_order"}:
        assert response.status_code == 409, response.text
        gateway.assert_not_awaited()
        assert _get_order(order_id).payment_invoice_id is None
        return
    assert response.status_code == 200, response.text
    fields, document_links = [call.args[1] for call in crm_fields.await_args_list[:2]]
    assert fields[crm.CF["cash_due"]] == float(cash)
    assert fields[crm.CF["balance_spent"]] == display_spent_rubles(applied)
    assert document_links[crm.CF["ms_invoice_id"]] == str(IID)
    assert response.json()["order_id"] == order_id
    assert response.json()["awaiting_settlement"] is False
    assert Decimal(str(response.json()["amount_rubles"])) == cash
    assert _get_order(order_id).grand_total == cash
    if scenario in {"full", "full_exact_balance"}:
        gateway.assert_not_awaited()
        assert response.json()["is_paid"] is True
        assert _get_order(order_id).payment_provider == "moysklad_balance"
        retry = client.post("/api/v1/payments/create", headers=headers, json={"order_id": order_id})
        assert retry.status_code == 200, retry.text
        assert retry.json()["is_paid"] is True
        gateway.assert_not_awaited()
    else:
        assert gateway.call_args.kwargs["amount_rub"] == cash
        if scenario in {"retry", "not_ready"}:
            retry = client.post("/api/v1/payments/create", headers=headers, json={"order_id": order_id})
            assert retry.status_code == 200, retry.text
            assert retry.json()["invoice_id"] == "mock-invoice-1"
        gateway.assert_awaited_once()
    crm.amocrm_client.add_lead_note.assert_awaited_once()
    assert str(cash.quantize(Decimal("0.01"))) in crm.amocrm_client.add_lead_note.call_args.args[1]


def test_settlement_lock_rejects_overlap_and_releases_after_failure(monkeypatch):
    async def check():
        engine = create_async_engine(settlement_payment.engine.url)
        monkeypatch.setattr(settlement_payment, "engine", engine)
        try:
            with pytest.raises(RuntimeError, match="test failure"):
                async with settlement_payment.settlement_lock(CID):
                    with pytest.raises(HTTPException) as error:
                        async with settlement_payment.settlement_lock(CID):
                            pytest.fail("Overlapping balance checkout acquired the lock")
                    assert error.value.status_code == 409
                    raise RuntimeError("test failure")
            async with settlement_payment.settlement_lock(CID):
                pass
        finally:
            await engine.dispose()
    asyncio.run(check())
