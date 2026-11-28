from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.app.services.orders import crm
from src.integrations.amocrm.constants import CF
from src.integrations.amocrm.payloads import build_lead_custom_fields
from src.integrations.moysklad.order_sync.attributes import _moysklad_attr_values


@pytest.fixture
def anyio_backend():
    return "asyncio"


def order_for(benefits, **overrides):
    return SimpleNamespace(**{
        "checkout_snapshot": {"benefits": benefits}, "order_number": "EP-TEST",
        "amocrm_lead_id": None, "moysklad_customerorder_id": None, "comment": None,
        "grand_total": Decimal("2236.55"), "delivery_total": Decimal("423.55"),
        "payment_method": "later", "selected_delivery_service": "CDEK", **overrides,
    })


@pytest.mark.parametrize("benefits,expected", [
    ({"entered_code": "ХРЮН_СЛИМ", "ms_order_promo": "хрюн_слим"}, "хрюн_слим"),
    ({"entered_code": None, "ms_order_promo": "Partner"}, "Partner"),
    ({"entered_code": "NOT-APPLIED", "ms_order_promo": None}, None),
    ({"entered_code": "Legacy"}, "Legacy"),
    ({"applications": [{"source_kind": "app_welcome", "code": "WELCOME"}]}, None),
    ({}, None),
])
def test_amo_creation_and_ms_export_agree(benefits, expected):
    order = order_for(benefits)
    fields = {f.field_id: f.values[0].value
              for f in build_lead_custom_fields(crm._checkout_lead_fields(order, "address"))}
    attrs = _moysklad_attr_values(order)
    if expected is None:
        assert 752923 not in fields and "promo_code" not in attrs
    else:
        assert fields[752923] == attrs["promo_code"] == expected


@pytest.mark.anyio
@pytest.mark.parametrize("known", [True, False])
@pytest.mark.parametrize("remote,linked", [(None, False), ("Partner", False), ("Other", False), (None, True)])
async def test_retry_only_fills_missing_promo_on_an_unexported_lead(monkeypatch, known, remote, linked):
    fields = []
    if remote:
        fields.append({"field_id": 752923, "values": [{"value": remote}]})
    if linked:
        fields.append({"field_id": CF["ms_order_id"], "values": [{"value": "ms-id"}]})
    lead = {"id": 17, "custom_fields_values": fields}
    amo = AsyncMock()
    amo.get_lead.return_value = amo.find_lead_by_order_number.return_value = lead
    monkeypatch.setattr(crm, "amocrm_client", amo)
    order = order_for({"ms_order_promo": "Partner"}, amocrm_lead_id=17 if known else None)
    session = SimpleNamespace(flush=AsyncMock())
    if remote == "Other":
        with pytest.raises(HTTPException) as exc:
            await crm.ensure_order_has_amocrm_lead(session, order, user=None)
        assert exc.value.status_code == 409
    else:
        assert await crm.ensure_order_has_amocrm_lead(session, order, user=None) == 17
    if not linked and remote is None:
        amo.update_lead_order_fields.assert_awaited_once_with(17, {752923: "Partner"})
    else:
        amo.update_lead_order_fields.assert_not_awaited()
    amo.create_lead_with_contact_and_note.assert_not_awaited()


@pytest.mark.anyio
async def test_no_rebinding_after_export(monkeypatch):
    amo = AsyncMock()
    monkeypatch.setattr(crm, "amocrm_client", amo)
    order = order_for({"ms_order_promo": "Partner"}, amocrm_lead_id=17, moysklad_customerorder_id="ms-id")
    assert await crm.ensure_order_has_amocrm_lead(None, order, user=None) == 17
    assert not amo.mock_calls
