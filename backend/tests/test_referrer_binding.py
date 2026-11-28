from copy import deepcopy
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.app.services.referrals import bind


@pytest.fixture
def binding(monkeypatch):
    buyer, owner = uuid4(), uuid4()
    attrs = {bind.PROGRAM_ATTRIBUTE_ID: {"name": "Бонусная"}, bind.DISCOUNT_ATTRIBUTE_ID: 0}
    card = {"id": str(buyer), "tags": ["Клиенты"], "salesAmount": 0}
    async def get(cid):
        assert cid == buyer
        return deepcopy(dict(card, attributes=[{"id": k, "value": v} for k, v in attrs.items()]))
    async def patch(kind, cid, data):
        assert (kind, cid) == ("counterparty", buyer)
        for a in data["attributes"]:
            attrs[a["id"]] = a["value"]
        card.update({k: v for k, v in data.items() if k != "attributes"})
    async def attribute(key, *, text=None, code=None, number=None):
        return {"id": key, "value": text if text else {"name": "Реферальная"} if code == 2 else number}
    client = SimpleNamespace(get_counterparty=get, _update_entity=AsyncMock(side_effect=patch))
    resolver = AsyncMock(return_value=SimpleNamespace(code="Хрюн_Слим", id=owner))
    monkeypatch.setattr(bind, "resolve_ms_referrer", resolver)
    monkeypatch.setattr(bind, "require_no_competing_referral", AsyncMock())
    monkeypatch.setattr(bind, "_attribute_builder", AsyncMock(return_value=attribute))
    monkeypatch.setattr(bind, "invalidate_account_settlement", AsyncMock())
    return buyer, client, attrs, card, resolver


@pytest.mark.anyio
async def test_apply_binds_buyer_before_order_and_same_code_is_idempotent(binding):
    cid, client, attrs, card, resolver = binding
    binding = await bind._bind_card(None, client, cid, "хрюн_слим")
    assert binding.code == "Хрюн_Слим"
    assert binding.owner_id == resolver.return_value.id
    resolver.assert_awaited_once_with("хрюн_слим", buyer_id=cid, client=client)
    assert attrs[bind.REFERRER_ATTRIBUTE_ID] == "Хрюн_Слим"
    assert card["tags"] == ["Клиенты", "пришёл по промокоду"]
    assert attrs[bind.PROGRAM_ATTRIBUTE_ID]["name"] == "Реферальная"
    assert attrs[bind.DISCOUNT_ATTRIBUTE_ID] == 3
    assert await bind._bind_card(None, client, cid, "ХРЮН_СЛИМ") == binding
    client._update_entity.assert_awaited_once()
    with pytest.raises(HTTPException) as conflict:
        await bind._bind_card(None, client, cid, "other")
    assert conflict.value.status_code == 409
    client._update_entity.assert_awaited_once()


@pytest.mark.anyio
async def test_invalid_owner_and_unconfirmed_write_never_return_success(binding):
    cid, client, _, _, resolver = binding
    resolver.side_effect = HTTPException(422, "Invalid code")
    with pytest.raises(HTTPException):
        await bind._bind_card(None, client, cid, "unknown")
    client._update_entity.assert_not_awaited()
    resolver.side_effect = None
    client._update_entity.side_effect = None
    with pytest.raises(ValueError, match="not confirmed"):
        await bind._bind_card(None, client, cid, "хрюн_слим")


@pytest.mark.anyio
async def test_binding_does_not_lower_existing_accounting_discount(binding):
    cid, client, attrs, _, _ = binding
    attrs[bind.DISCOUNT_ATTRIBUTE_ID] = 17
    await bind._bind_card(None, client, cid, "хрюн_слим")
    assert attrs[bind.DISCOUNT_ATTRIBUTE_ID] == 17


@pytest.mark.anyio
async def test_account_binding_only_mirrors_verified_buyer_and_fails_closed_for_shared_card(binding, monkeypatch):
    cid, client, _, _, _ = binding
    user = SimpleNamespace(id=77, moysklad_counterparty_id=cid, is_verified=True, promo_code=None)
    profile = SimpleNamespace(reward_program="bonus", reward_program_selected_at=None, reward_program_snapshot={})
    @asynccontextmanager
    async def lock(_):
        yield
    ids = [77, 78]
    db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: ids)), commit=AsyncMock())
    monkeypatch.setattr(bind, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    monkeypatch.setattr(bind, "settlement_lock", lock)
    monkeypatch.setattr(bind, "lock_order_referrer", AsyncMock())
    monkeypatch.setattr(bind, "get_moysklad_client", lambda: client)
    monkeypatch.setattr(bind, "get_or_create_referral_profile", AsyncMock(return_value=profile))
    with pytest.raises(HTTPException) as exc:
        await bind.bind_referrer(db, user=user, code="хрюн_слим")
    assert exc.value.status_code == 409
    client._update_entity.assert_not_awaited()
    assert user.promo_code is None
    ids.pop()
    assert await bind.bind_referrer(db, user=user, code="хрюн_слим") == "Хрюн_Слим"
    assert profile.reward_program == "partner"
    assert profile.reward_program_snapshot["moysklad_referrer_promo"] == user.promo_code == "Хрюн_Слим"
    db.commit.assert_awaited_once()
