import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.integrations.moysklad.order_sync import states
from src.app.services.orders import crm


@pytest.mark.parametrize("state", [
    {"name": "Груз доставлен / Успех", "stateType": "Regular"},
    {"name": "Груз укомплектован", "stateType": "Regular"},
    {"name": "Наложенный платеж", "stateType": "Regular"},
    {"name": "Груз отправлен", "stateType": "Regular"},
    {"name": "Custom success", "stateType": "Successful"},
    {"name": "Custom canceled", "stateType": "Unsuccessful"},
])
def test_late_payment_state_does_not_rewind_moysklad(monkeypatch, state):
    state = dict(state, meta={"href": "https://example.test/state/later"})
    target = {"meta": {"href": "https://example.test/state/paid"}}
    client = SimpleNamespace(is_configured=lambda: True,
        find_customerorder_state_by_name=AsyncMock(return_value=target),
        get_customer_order=AsyncMock(return_value={"state": state}),
        update_customer_order_state=AsyncMock())
    monkeypatch.setattr(states, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    monkeypatch.setattr(states, "get_moysklad_client", lambda: client)
    order = SimpleNamespace(id=7, moysklad_customerorder_id="order")
    assert asyncio.run(states.sync_moysklad_customerorder_state(order, state_name="Счет оплачен")) is False
    client.update_customer_order_state.assert_not_awaited()


@pytest.mark.parametrize("payment", ["paid", "hold", "partial", "error"])
def test_late_payment_does_not_reopen_completed_amo_lead(monkeypatch, payment):
    update = AsyncMock()
    monkeypatch.setattr(crm.amocrm_client, "update_lead_status", update)
    order = SimpleNamespace(id=7, is_shipped=True, is_canceled=False, is_active=False)
    assert asyncio.run(crm._move_lead_to_payment_result_status(None, order, payment_status=payment)) is order
    update.assert_not_awaited()
