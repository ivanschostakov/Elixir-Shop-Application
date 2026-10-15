import asyncio
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import create_async_engine

import config
from src.database.models import User
from src.app.services.benefits import service as benefits, moysklad_bonus
from src.app.services.orders import creation, settlement_payment, crm
from src.integrations.moysklad.settlement_checkout import display_spent_rubles
from test_settlement_checkout import CID, CURRENCY, IID, OID, ORG, documents, ref
from test_orders_api import (
    registered_user, variant_factory, stub_amocrm, sync_engine,
    _create_ready_draft, _get_order, _update_order,
)


@pytest.mark.parametrize("scenario", ["exact", "rounded", "full", "full_exact_balance", "partial_delivery", "wrong_invoice",
    "balance_changed", "not_ready", "cancelled", "retry", "other_open_order"])
def test_balance_checkout_api_uses_only_mocked_external_services(
    client, registered_user, variant_factory, stub_amocrm, monkeypatch, scenario,
):
    monkeypatch.setattr(config, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    monkeypatch.setattr(config, "LOYALTY_SETTLEMENT_CHECKOUT_ENABLED", True)
    monkeypatch.setattr(crm.amocrm_client, "update_lead_price", AsyncMock(), raising=False)
    monkeypatch.setattr(crm.amocrm_client, "add_lead_note", AsyncMock(), raising=False)
    balance = Decimal("300") if scenario == "partial_delivery" else Decimal("399") if scenario == "full_exact_balance" else Decimal("1000")
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
    remote["invoicesOut"] = [ref(IID)]
    ms = SimpleNamespace(
        entity_href=lambda *args: "https://example.test/agent",
        get_page=AsyncMock(return_value={"rows": []}),
        get_customer_order=AsyncMock(return_value=remote), get_invoiceout=AsyncMock(return_value=invoice),
    )
    monkeypatch.setattr(settlement_payment, "get_moysklad_client", lambda: ms)
    monkeypatch.setattr(settlement_payment, "verify_ruble_currency", AsyncMock(return_value=CURRENCY))
    monkeypatch.setattr(settlement_payment.asyncio, "sleep", AsyncMock())

    async def sync_mock(db, *, order, user):
        # Persistence is real; MoySklad documents and gateway calls are fixtures only.
        snapshot = deepcopy(order.checkout_snapshot)
        snapshot["settlement_payment"]["organization_id"] = str(ORG)
        order.checkout_snapshot = snapshot
        order.moysklad_customerorder_id = OID
        await db.commit()
    monkeypatch.setattr(creation, "sync_order_to_moysklad_safe", sync_mock)
    monkeypatch.setattr(creation, "_enrich_selected_delivery_address_payload", AsyncMock())
    gateway = AsyncMock(return_value={"Result": {"InvoiceId": "mock-invoice-1"}})
    state = {"Result": {"PaymentStep": "Created", "Form3DS": '{"SbpQrCodeUrl":"https://example.test/qr"}'}}
    monkeypatch.setattr("src.app.services.orders.intellectmoney.create_invoice", gateway)
    monkeypatch.setattr("src.app.services.orders.intellectmoney.sbp_payment", AsyncMock(return_value=state))
    monkeypatch.setattr("src.app.services.orders.intellectmoney.get_bank_card_payment_state", AsyncMock(return_value=state))
    monkeypatch.setattr("src.app.services.orders._resolve_payment_qr_image", AsyncMock(return_value=None))
    catalog = variant_factory(price=price)
    headers = registered_user["headers"]
    draft = _create_ready_draft(client, headers, catalog["variant_id"])
    for use_balance in (False, True):
        preview = client.post("/api/v1/users/me/benefits/check", headers=headers, json={
            "draft_id": draft["id"], "use_bonus_rubles": use_balance})
        assert preview.status_code == 200, preview.text
        expected_cash = max(Decimal("0"), gross - balance) if use_balance else gross
        assert Decimal(preview.json()["cash_total"]) == expected_cash
        assert Decimal(preview.json()["total_after_discounts"]) >= 0
    response = client.post("/api/v1/users/me/orders", headers=headers, json={
        "draft_id": draft["id"], "payment_method": "sbp", "use_bonus_rubles": True})
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["grand_total"]) == max(Decimal("0"), gross - balance)
    order_id = response.json()["id"]
    assert response.json()["checkout_snapshot"]["settlement_payment"]["gross_rubles"] == str(gross.quantize(Decimal("0.01")))
    if scenario == "wrong_invoice": invoice["customerOrder"] = ref(CID)
    if scenario == "balance_changed":
        moysklad_bonus.get_moysklad_settlement_wallet.return_value = SimpleNamespace(balance_rubles=Decimal("0"))
    if scenario == "not_ready": remote["invoicesOut"] = []
    if scenario == "cancelled": _update_order(order_id, is_canceled=True)
    if scenario == "other_open_order":
        ms.get_page.return_value = {"rows": [{"id": str(CID), "sum": 10000, "shippedSum": 0}]}
    response = client.post("/api/v1/payments/create", headers=headers, json={"order_id": order_id})
    if scenario in {"wrong_invoice", "balance_changed", "not_ready", "cancelled", "other_open_order"}:
        assert response.status_code == 409, response.text
        gateway.assert_not_awaited()
        assert _get_order(order_id).payment_invoice_id is None
        return
    assert response.status_code == 200, response.text
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
        if scenario == "retry":
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
