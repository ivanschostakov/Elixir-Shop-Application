from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.app.services.orders import crm
from src.app.services.referrals import promo
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


BUYER, OWNER = str(uuid4()), str(uuid4())


def verified(code, owner=OWNER):
    return {"ms_order_promo": code, "ms_promo_buyer_id": BUYER, "ms_referrer_id": owner}


@pytest.mark.parametrize("benefits,expected", [
    ({"entered_code": "ХРЮН_СЛИМ", **verified("хрюн_слим")}, "хрюн_слим"),
    ({"entered_code": None, **verified("Partner")}, "Partner"),
    (verified("Company", None), "Company"),
    (verified("Unknown", None), None),
    (verified("Не указан"), None),
    (verified(" НЕ  УКАЗАНО "), None),
    (verified({"value": "Partner"}), None),
    (verified("Partner", BUYER), None),
    (verified("Partner", "invalid-id"), None),
    ({"ms_order_promo": "Partner"}, None),
    ({"entered_code": "NOT-APPLIED", "ms_order_promo": None}, None),
    ({"entered_code": "Legacy"}, None),
    ({"applications": [{"source_kind": "app_welcome", "code": "WELCOME"}]}, None),
    ({}, None),
])
def test_amo_creation_and_ms_export_agree(monkeypatch, benefits, expected):
    monkeypatch.setattr("src.integrations.moysklad.order_sync.attributes.LOYALTY_COMPANY_PROMO_CODE", "Company")
    order = order_for(benefits)
    order.checkout_snapshot["moysklad"] = {"promo_code": "raw", "attributes": {"promo_code": "raw-attribute"}}
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
    order = order_for(verified("Partner"), amocrm_lead_id=17 if known else None)
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
    order = order_for(verified("Partner"), amocrm_lead_id=17, moysklad_customerorder_id="ms-id")
    assert await crm.ensure_order_has_amocrm_lead(None, order, user=None) == 17
    assert not amo.mock_calls


@pytest.mark.anyio
@pytest.mark.parametrize("response", [{}, {"promo": "different"}, {"promo": "Не указан"}, {"promo": {"name": "CODE"}}])
async def test_profile_does_not_accept_an_unconfirmed_code_even_if_locally_cached(monkeypatch, response):
    profile = SimpleNamespace(reward_program_selection_source="system_default")
    user = SimpleNamespace(promo_code="CODE", moysklad_counterparty_id=None)
    site = AsyncMock()
    site.lookup.return_value = response
    monkeypatch.setattr(promo, "_get_program_profile", AsyncMock(return_value=profile))
    monkeypatch.setattr(promo, "bitrix_promo_configured", lambda: True)
    monkeypatch.setattr(promo, "BitrixPromoClient", lambda: site)
    with pytest.raises(HTTPException) as exc:
        await promo.attach_referrer_code(None, user=user, code="code")
    assert exc.value.status_code == 503
    site.lookup.assert_awaited_once_with("CODE")
    site.attach_referrer.assert_not_awaited()


@pytest.mark.anyio
async def test_retry_with_unverified_legacy_input_does_not_touch_existing_amo_field(monkeypatch):
    amo = AsyncMock()
    monkeypatch.setattr(crm, "amocrm_client", amo)
    order = order_for({"entered_code": "Не указан"}, amocrm_lead_id=17)
    assert await crm.ensure_order_has_amocrm_lead(None, order, user=None) == 17
    assert not amo.mock_calls
