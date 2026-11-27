import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from src.app.services.referrals import milestones as m, ms_codes


def setup_client(monkeypatch, spend="30000", program="Бонусная", own="", incoming="", rate=0):
    cid = uuid4()
    values = {m.PROGRAM_ATTRIBUTE_ID: {"name": program}, m.DISCOUNT_ATTRIBUTE_ID: rate,
              m.OWN_PROMO_ATTRIBUTE_ID: own, m.REFERRER_ATTRIBUTE_ID: incoming}
    def card(*_):
        return {"id": str(cid), "salesAmount": int(Decimal(spend)*100),
                "attributes": [{"id": key, "value": val} for key, val in values.items()]}
    async def attribute(key, *, code=None, number=None, text=None):
        return {"id": key, "value": {"name": "Партнерская"} if code == 2 else
                number if number is not None else text}
    async def update(entity, oid, patch):
        assert entity == "counterparty" and oid == cid and set(patch) == {"attributes"}
        values.update({v["id"]: v["value"] for v in patch["attributes"]})
    client = SimpleNamespace(get_counterparty=AsyncMock(side_effect=card), _update_entity=AsyncMock(side_effect=update))
    monkeypatch.setattr(m, "_attribute_builder", AsyncMock(return_value=attribute))
    monkeypatch.setattr(m, "find_ms_code_owners", AsyncMock(return_value={}))
    monkeypatch.setattr(m, "invalidate_account_settlement", AsyncMock())
    monkeypatch.setattr(m, "LOYALTY_COMPANY_PROMO_CODE", "Elixir")
    return cid, client, values


@pytest.mark.parametrize("spend,offer,issue", [("29999.99",False,False),("30000",True,False),
    ("99999.99",True,False),("100000",True,True)])
def test_thresholds_and_idempotency(monkeypatch, spend, offer, issue):
    cid, client, vals = setup_client(monkeypatch, spend=spend)
    first = asyncio.run(m._update_locked(client, cid, accept=False))
    again = asyncio.run(m._update_locked(client, cid, accept=False))
    assert first == again and first["offer_partner"] is offer and first["own_code_eligible"] is issue
    assert bool(first["own_promo_code"]) is issue and client._update_entity.await_count == int(issue)
    assert vals[m.PROGRAM_ATTRIBUTE_ID]["name"] == "Бонусная" and not vals[m.REFERRER_ATTRIBUTE_ID]


def test_consent_sets_company_not_owner_and_preserves_existing_personal_code(monkeypatch):
    cid, client, vals = setup_client(monkeypatch, spend="100000", own="MY-OLD")
    result = asyncio.run(m._update_locked(client, cid, accept=True))
    assert result == asyncio.run(m._update_locked(client, cid, accept=True))
    assert not result["offer_partner"] and result["own_promo_code"] == "MY-OLD"
    assert vals[m.REFERRER_ATTRIBUTE_ID] == "Elixir" and vals[m.DISCOUNT_ATTRIBUTE_ID] == 3
    assert vals[m.PROGRAM_ATTRIBUTE_ID]["name"] == "Партнерская"
    client._update_entity.assert_awaited_once()


@pytest.mark.parametrize("setup", [{"spend":"29999.99"},{"incoming":"INVITER"},{"rate":25},
                                  {"program":"Партнерская","incoming":"OLD"}])
def test_does_not_overwrite_other_attribution_or_bypass_threshold(monkeypatch, setup):
    cid, client, _ = setup_client(monkeypatch, **setup)
    with pytest.raises(HTTPException) as err:
        asyncio.run(m._update_locked(client, cid, accept=True))
    assert err.value.status_code == 409
    client._update_entity.assert_not_awaited()


def test_check_uses_settlement_cache_until_issuance_is_needed(monkeypatch):
    cid = uuid4()
    monkeypatch.setattr(m, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    view = SimpleNamespace(status="fresh",total_purchases_rubles=Decimal("30000"),loyalty_program=1,
                           own_promo_code=None,referrer_promo_code=None)
    monkeypatch.setattr(m, "get_account_settlement", AsyncMock(return_value=view))
    monkeypatch.setattr(m, "settlement_lock", lambda *_: pytest.fail("no writes during eligibility read"))
    user = SimpleNamespace(is_verified=True, moysklad_counterparty_id=cid)
    assert asyncio.run(m.check_milestones(None,user=user))["offer_partner"]
    view.status = "stale"
    with pytest.raises(HTTPException) as exc:
        asyncio.run(m.check_milestones(None,user=user))
    assert exc.value.status_code == 503


def test_collision_and_failed_readback_do_not_announce_code(monkeypatch):
    cid, client, _ = setup_client(monkeypatch, spend="100000")
    monkeypatch.setattr(m, "find_ms_code_owners", AsyncMock(return_value={uuid4():object()}))
    with pytest.raises(HTTPException):
        asyncio.run(m._update_locked(client, cid, accept=False))
    client._update_entity.assert_not_awaited()
    monkeypatch.setattr(m, "find_ms_code_owners", AsyncMock(return_value={}))
    client._update_entity.side_effect = None
    with pytest.raises(ValueError, match="not confirmed"):
        asyncio.run(m._update_locked(client, cid, accept=False))


def test_personal_invite_remains_usable_without_converting_owner(monkeypatch):
    cid = uuid4()
    code = m.milestone_code(cid)
    monkeypatch.setattr(ms_codes,"find_ms_code_owners",AsyncMock(return_value={cid:(code,1,Decimal(0))}))
    assert asyncio.run(ms_codes.resolve_ms_referrer(code,client=object())).id == cid
    with pytest.raises(HTTPException):
        asyncio.run(ms_codes.resolve_ms_referrer(code,buyer_id=cid,client=object()))


def test_company_invitation_cannot_be_claimed_by_private_owner(monkeypatch):
    monkeypatch.setattr(ms_codes, "LOYALTY_COMPANY_PROMO_CODE", "Elixir")
    monkeypatch.setattr(ms_codes, "find_ms_code_owners", AsyncMock(return_value={
        uuid4(): ("ELIXIR", 2, Decimal(100000))
    }))
    with pytest.raises(HTTPException) as err:
        asyncio.run(ms_codes.resolve_ms_referrer("elixir", client=object()))
    assert err.value.status_code == 409


@pytest.mark.parametrize("code,spend,status", [("Friend", None, None), ("elixir", None, 503),
    ("elixir", Decimal("29999.99"), 409), ("ELIXIR", Decimal("30000"), None)])
def test_manual_codes_before_threshold(monkeypatch, code, spend, status):
    monkeypatch.setattr(ms_codes, "LOYALTY_COMPANY_PROMO_CODE", "Elixir")
    params = dict(code=code, program=1, incoming=None, spend=spend)
    if status:
        with pytest.raises(HTTPException) as exc:
            ms_codes.check_company_threshold(**params)
        assert exc.value.status_code == status
    else:
        ms_codes.check_company_threshold(**params)


def test_offer_acceptance_honors_unprocessed_order_attribution(monkeypatch):
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def lock(_):
        yield
    cid = uuid4()
    db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [7])),
                         execute=AsyncMock(), scalar=AsyncMock(return_value=42))
    monkeypatch.setattr(m, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    monkeypatch.setattr(m, "settlement_lock", lock)
    monkeypatch.setattr(m, "get_moysklad_client", lambda: pytest.fail("must not modify MoySklad"))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(m.check_milestones(db, user=SimpleNamespace(id=7, is_verified=True,
                                       moysklad_counterparty_id=cid), accept=True))
    assert exc.value.status_code == 409
    db.execute.assert_awaited_once()
