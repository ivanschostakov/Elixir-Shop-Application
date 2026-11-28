import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from src.app.services.benefits import service
from src.app.services.benefits.moysklad_bonus import MoySkladBonusWallet
from src.app.services.benefits.settlement import OWN_PROMO_ATTRIBUTE_ID, PROGRAM_ATTRIBUTE_ID
from src.app.services.referrals import ms_codes
from src.app.services.orders.creation.snapshots import _json_safe_benefits
from src.integrations.moysklad.order_sync.attributes import customerorder_promo_code


def row(code, program="Партнерская", **fields):
    return {"id": str(uuid4()), "attributes": [
        {"id": OWN_PROMO_ATTRIBUTE_ID, "value": code},
        {"id": PROGRAM_ATTRIBUTE_ID, "value": {"name": program}}], **fields}


def client(rows):
    return SimpleNamespace(is_configured=lambda: True, base_url="https://ms.test", get_page=AsyncMock(
        return_value={"meta": {"size": len(rows)}, "rows": rows}))


def test_exact_partner_match_uses_canonical_case_and_id():
    owner = row("хрюн_слим")
    ms = client([row("хрюн_слим2"), row("хрюн_слим", archived=True), owner])
    result = asyncio.run(ms_codes.resolve_ms_referrer("ХРЮН_СЛИМ", client=ms))
    assert (result.code, str(result.id)) == ("хрюн_слим", owner["id"])
    assert ms.get_page.await_args.kwargs["filter"].endswith("~ХРЮН_СЛИМ")


@pytest.mark.parametrize("kind,status", [("self",422),("duplicate",409),("bonus",422),("unknown",422),
                                           ("malformed",422),("incomplete",503),("offline",503)])
def test_invalid_owner_never_means_zero_discount_checkout(kind, status):
    buyer = uuid4()
    rows = {"self":[row("test", id=str(buyer))], "duplicate":[row("test"),row("TEST")],
            "bonus":[row("test", "Бонусная")]}.get(kind, [])
    ms = client(rows)
    if kind == "offline": ms.get_page.side_effect = RuntimeError("offline")
    if kind == "incomplete": ms.get_page.return_value["meta"]["size"] = 1
    with pytest.raises(HTTPException) as error:
        asyncio.run(ms_codes.resolve_ms_referrer("a;b" if kind == "malformed" else "test", buyer_id=buyer, client=ms))
    assert error.value.status_code == status


def test_configured_company_code_is_not_a_private_payee(monkeypatch):
    monkeypatch.setattr(ms_codes, "LOYALTY_COMPANY_PROMO_CODE", "Elixir")
    assert asyncio.run(ms_codes.resolve_ms_referrer("ELIXIR", client=client([]))) == ms_codes.ReferralOwner("Elixir", None)


@pytest.mark.parametrize("code", ["Не указан", "  НЕ  УКАЗАНО  ", "не\u00a0указан", "", None, 17])
def test_placeholder_cannot_even_be_a_configured_or_registered_code(monkeypatch, code):
    ms = client([row(code)])
    monkeypatch.setattr(ms_codes, "LOYALTY_COMPANY_PROMO_CODE", code)
    with pytest.raises(HTTPException) as error:
        asyncio.run(ms_codes.resolve_ms_referrer(code, client=ms))
    assert error.value.status_code == 422
    ms.get_page.assert_not_awaited()


@pytest.mark.parametrize("program,attached,rate,entered,mode,expected,rebate", [
    (2,None,0,"ХРЮН_СЛИМ","order_referral",30,0),
    (2,"хрюн_слим",8,None,None,80,0),
    (2,None,8,None,None,80,0),
    (1,None,0,"ХРЮН_СЛИМ","order_referral",30,0),
    (1,None,0,"OLD","promo",0,5),
])
def test_ms_quote_and_export(monkeypatch, program, attached, rate, entered, mode, expected, rebate):
    cid, rid = uuid4(), uuid4()
    user = SimpleNamespace(id=1, moysklad_counterparty_id=cid, promo_code=attached or "STALE-LOCAL")
    profile = SimpleNamespace(id=4, reward_program="partner" if program == 2 else "bonus",
        reward_program_selection_source="moysklad", reward_program_snapshot={"moysklad_program_code":program,
        "moysklad_referrer_promo":attached,"moysklad_discount_percent":str(rate)},
        current_discount_percent=Decimal(rate))
    lookup = AsyncMock(return_value=ms_codes.ReferralOwner("хрюн_слим",rid))
    monkeypatch.setattr(service, "resolve_ms_referrer", lookup)
    monkeypatch.setattr(service, "get_basket_by_user_id", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "ensure_default_reward_program", AsyncMock(return_value=profile))
    monkeypatch.setattr("src.app.services.benefits.settlement.get_account_settlement", AsyncMock(return_value=SimpleNamespace(status="fresh", referrer_promo_code=attached)))
    monkeypatch.setattr(service, "get_user_moysklad_bonus_wallet", AsyncMock(return_value=MoySkladBonusWallet(is_loaded=True,is_settlement=True,counterparty_id=cid)))
    monkeypatch.setattr(service, "pending_loyalty_bonus_points", AsyncMock(return_value=0))
    monkeypatch.setattr(service, "_rounded_personal_discount", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "BitrixPromoClient", lambda: pytest.fail("website must not validate an MS referral"))
    q = asyncio.run(service.resolve_benefits_for_user(SimpleNamespace(),user=user,entered_code=entered,
        reward_mode=mode,subtotal=Decimal("1500"),discountable_subtotal=Decimal("1000"),delivery_total=Decimal("300"),quote_items=[]))
    assert q["cashback_percent"] == rebate
    assert q["stacked_discount_amount"] == expected
    assert q["cash_total"] == 1800 - expected
    assert user.promo_code == (attached or "STALE-LOCAL")
    if expected and (attached or entered):
        snapshot = _json_safe_benefits(q)
        assert snapshot["ms_order_promo"] == snapshot["entered_code"] == "хрюн_слим"
        assert snapshot["ms_referrer_id"] == str(rid)
        assert customerorder_promo_code({"benefits":snapshot}) == "хрюн_слим"
    else:
        lookup.assert_not_awaited()
        assert q["ms_order_promo"] is None and q["ms_referrer_id"] is None
        assert all(not a["code"] for a in q["stacked_discount_options"] if a["source_kind"] == "app_referral")


@pytest.mark.parametrize("change", ["none", "placeholder", "owner", "buyer", "incoming"])
def test_worker_rechecks_frozen_attribution(change):
    from src.app.services.benefits.settlement import REFERRER_ATTRIBUTE_ID
    buyer = uuid4()
    partner = row("Friend")
    ms = client([partner])
    ms.get_counterparty = AsyncMock(return_value={"id":str(buyer), "attributes":[
        {"id":REFERRER_ATTRIBUTE_ID, "value":{"incoming":"other", "placeholder":"Не указан"}.get(change, "friend")}]})
    snapshot = {"ms_order_promo":"Friend", "ms_referrer_id":str(uuid4()) if change == "owner" else partner["id"],
                "ms_promo_buyer_id": str(uuid4() if change=="buyer" else buyer)}
    op = ms_codes.verify_referral_export(snapshot, buyer_id=buyer, client=ms)
    if change in {"none", "placeholder"}:
        asyncio.run(op)
    else:
        with pytest.raises(ValueError):
            asyncio.run(op)


@pytest.mark.parametrize("change,status", [("none",0), ("rate",409), ("incoming",409), ("pending",409), ("excluded",422)])
def test_checkout_rechecks_buyer_before_order(monkeypatch, change, status):
    from src.app.services.orders.creation import benefits
    from src.app.services.benefits.settlement import DISCOUNT_ATTRIBUTE_ID, REFERRER_ATTRIBUTE_ID
    buyer=uuid4()
    card=row("",id=str(buyer))
    card["attributes"] += [{"id":DISCOUNT_ATTRIBUTE_ID,"value":{"name":"6" if change=="rate" else "0"}},
                            {"id":REFERRER_ATTRIBUTE_ID, "value":"other" if change=="incoming" else "Не указан"}]
    monkeypatch.setattr(benefits, "get_moysklad_client", lambda: SimpleNamespace(get_counterparty=AsyncMock(return_value=card)))
    session=SimpleNamespace(execute=AsyncMock(), scalar=AsyncMock(return_value=42 if change=="pending" else None))
    resolved={"ms_order_promo":"Friend","ms_promo_buyer_state":{"program":2,"incoming":None,"discount":"0"},
              "stacked_discount_options":[{"source_kind":"app_referral","applied_discount_amount":0 if change=="excluded" else 30}]}
    op=benefits._verify_order_referral(session, SimpleNamespace(moysklad_counterparty_id=buyer), resolved)
    if not status:
        asyncio.run(op)
    else:
        with pytest.raises(HTTPException) as exc: asyncio.run(op)
        assert exc.value.status_code == status
