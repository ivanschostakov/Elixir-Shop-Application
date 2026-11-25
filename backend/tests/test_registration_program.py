import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.app.services.referrals import registration
from src.app.services.benefits import service as benefits
from src.app.services.benefits.moysklad_bonus import MoySkladBonusWallet
from src.app.services.benefits.settlement import PROGRAM_ATTRIBUTE_ID, DISCOUNT_ATTRIBUTE_ID, REFERRER_ATTRIBUTE_ID
from src.database.models import User, ReferralProfile
from src.integrations.moysklad.client import MoySkladClient
from test_orders_api import sync_engine, registered_user


@pytest.mark.parametrize("program,discount,cashback", [(1, "0", 50), (2, "40", 0), (0, "0", 0)])
def test_program_alone_selects_discount_or_cashback(monkeypatch, program, discount, cashback):
    cid = uuid4()
    profile = SimpleNamespace(id=1, reward_program="partner" if program == 2 else "bonus",
        reward_program_selection_source="moysklad", reward_program_snapshot={"moysklad_program_code": program,
            "moysklad_discount_percent": "4"}, referral_discount_base_total=Decimal("0"), current_discount_percent=Decimal("4"))
    monkeypatch.setattr(benefits, "get_basket_by_user_id", AsyncMock(return_value=None))
    monkeypatch.setattr(benefits, "ensure_default_reward_program", AsyncMock(return_value=profile))
    monkeypatch.setattr("src.app.services.benefits.settlement.get_account_settlement", AsyncMock(return_value=SimpleNamespace(status="fresh")))
    monkeypatch.setattr(benefits, "get_user_moysklad_bonus_wallet", AsyncMock(return_value=MoySkladBonusWallet(
        is_loaded=True, is_settlement=program in {1, 2}, counterparty_id=cid, balance_rubles=Decimal("0"))))
    monkeypatch.setattr(benefits, "pending_loyalty_bonus_points", AsyncMock(return_value=0))
    monkeypatch.setattr(benefits, "_rounded_personal_discount", AsyncMock(return_value=None))
    quote = asyncio.run(benefits.resolve_benefits_for_user(SimpleNamespace(),
        user=SimpleNamespace(id=1, moysklad_counterparty_id=cid, promo_code=None),
        entered_code="OLD-CLIENT-REQUEST" if program != 2 else None, reward_mode="promo", subtotal=Decimal("1000"),
        discountable_subtotal=Decimal("1000"), delivery_total=Decimal("0"), quote_items=[]))
    # Authoritative partner accounts reject a different order-level code.
    assert quote["cashback_earned_points"] == cashback
    assert quote["stacked_discount_amount"] == Decimal(discount)


def test_only_company_or_referrer_codes_can_select_partner_program(monkeypatch):
    monkeypatch.setattr(registration, "bitrix_promo_configured", lambda: True)
    lookup = AsyncMock(return_value={"promo": "Elixir", "is_firm_promo": True, "referral_owner_id": None})
    monkeypatch.setattr(registration, "BitrixPromoClient", lambda: SimpleNamespace(lookup=lookup))
    assert asyncio.run(registration.validate_registration_promo("Elixir")) == "Elixir"
    lookup.return_value = {"promo": "INVITE", "is_firm_promo": False, "referral_owner_id": 123}
    assert asyncio.run(registration.validate_registration_promo("INVITE")) == "INVITE"
    for invalid in ({"promo": "SALE", "is_firm_promo": False, "referral_owner_id": None}, {"promo": "OLD-API"}):
        lookup.return_value = invalid
        with pytest.raises(HTTPException):
            asyncio.run(registration.validate_registration_promo("SALE"))


def test_website_profile_cannot_replace_an_unfinished_registration_choice():
    from src.app.services.referrals.bitrix_sync import apply_bitrix_program_profile
    profile = SimpleNamespace(reward_program_selection_source="registration", reward_program="bonus",
        reward_program_snapshot={"registration_selection_required": True})
    user = SimpleNamespace(promo_code=None)
    apply_bitrix_program_profile(profile, user=user, program_profile={"referrer_promo": "OLD", "stored_discount_percent": 20})
    assert profile.reward_program_selection_source == "registration"
    assert user.promo_code is None


@pytest.mark.parametrize("program,promo,percent", [("bonus", None, 0), ("partner", "Elixir", 3), ("partner", "INVITE", 3)])
def test_new_customer_attributes_use_accounting_metadata(program, promo, percent):
    dictionary, bonus, partner = uuid4(), uuid4(), uuid4()
    def meta(kind, key): return {"href": f"https://example.test/entity/{kind}/{key}", "type": kind}
    rows = [{"id": PROGRAM_ATTRIBUTE_ID, "type": "customentity", "meta": meta("attributemetadata", PROGRAM_ATTRIBUTE_ID),
        "customEntityMeta": meta("customentity", f"{dictionary}/metadata")},
        {"id": DISCOUNT_ATTRIBUTE_ID, "type": "long", "meta": meta("attributemetadata", DISCOUNT_ATTRIBUTE_ID)},
        {"id": REFERRER_ATTRIBUTE_ID, "type": "string", "meta": meta("attributemetadata", REFERRER_ATTRIBUTE_ID)}]
    choices = [{"name": "Бонусная", "meta": meta("customentity", bonus)}, {"name": "Партнерская", "meta": meta("customentity", partner)}]
    client = SimpleNamespace(get_all=AsyncMock(side_effect=[rows, choices]))
    attrs = asyncio.run(registration._initial_attributes(client, program=program, promo=promo))
    assert client.get_all.await_args.args == (f"/entity/customentity/{dictionary}",)
    assert attrs[0]["value"]["meta"]["href"].endswith(str(bonus if program == "bonus" else partner))
    assert attrs[1]["value"] == percent
    assert [attr["value"] for attr in attrs[2:]] == ([promo] if promo else [])


def test_initial_attributes_are_never_written_to_an_existing_customer(monkeypatch):
    client = MoySkladClient(token="test", base_url="https://example.test/api")
    existing = {"id": str(uuid4()), "attributes": [{"value": "existing program"}]}
    monkeypatch.setattr(client, "_get_entity_by_id", AsyncMock(return_value=existing))
    create, update = AsyncMock(), AsyncMock()
    monkeypatch.setattr(client, "_create_entity", create)
    monkeypatch.setattr(client, "_update_entity", update)
    result = asyncio.run(client.get_or_create_counterparty(existing_counterparty_id=UUID(existing["id"]),
        external_code="app-1", sync_id=uuid4(), name="New name", email="a@example.test", phone=None,
        actual_address=None, initial_attributes=[{"value": "new program"}]))
    assert result == existing
    create.assert_not_awaited()
    update.assert_not_awaited()


def test_registration_alert_state_survives_relogin_and_existing_customer_cannot_be_switched(client, registered_user, monkeypatch):
    uid = registered_user["user_id"]
    with Session(sync_engine) as db:
        profile = db.query(ReferralProfile).filter_by(user_id=uid).one_or_none()
        if profile is None:
            profile = ReferralProfile(user_id=uid)
            db.add(profile)
        profile.reward_program_selection_source = "registration"
        profile.reward_program_snapshot = {"registration_selection_required": True}
        db.commit()
    response = client.get("/api/v1/auth/me", headers=registered_user["headers"])
    assert response.json()["program_selection_required"] is True
    with Session(sync_engine) as db:
        db.get(User, uid).moysklad_counterparty_id = uuid4()
        db.commit()
    record = AsyncMock(side_effect=AssertionError("Existing program must not be overwritten"))
    monkeypatch.setattr(registration, "record_registration_choice", record)
    monkeypatch.setattr("src.app.services.auth.service.counterparty._link_moysklad_counterparty_by_email", AsyncMock())
    response = client.post("/api/v1/auth/registration-program", headers=registered_user["headers"], json={"program": "bonus"})
    assert response.status_code == 200, response.text
    assert response.json()["program_selection_required"] is False
    record.assert_not_awaited()


@pytest.mark.parametrize("program,promo", [("bonus", None), ("partner", None), ("partner", "FRIEND")])
def test_new_registration_waits_for_alert_and_persists_choice_once(client, monkeypatch, program, promo):
    from test_orders_api import _delete_user
    from src.app.services.auth.service import sessions, counterparty
    welcome = AsyncMock()
    monkeypatch.setattr(sessions, "grant_welcome_bonus_safe", welcome)
    monkeypatch.setattr("src.app.services.benefits.loyalty.grant_welcome_bonus_safe", welcome)
    monkeypatch.setattr(counterparty, "_link_moysklad_counterparty_by_email", AsyncMock())
    monkeypatch.setattr(sessions, "_link_moysklad_counterparty_by_email", AsyncMock())
    lookup = AsyncMock(return_value={"promo": promo or "Elixir", "is_firm_promo": promo is None, "referral_owner_id": 123 if promo else None})
    monkeypatch.setattr(registration, "bitrix_promo_configured", lambda: True)
    monkeypatch.setattr(registration, "BitrixPromoClient", lambda: SimpleNamespace(lookup=lookup))
    attrs = [{"value": "metadata checked in separate tests"}]
    monkeypatch.setattr(registration, "_initial_attributes", AsyncMock(return_value=attrs))
    cid = uuid4()
    create = AsyncMock(return_value=SimpleNamespace(counterparty_id=cid, created=True))
    ms = SimpleNamespace(is_configured=lambda: True, get_page=AsyncMock(return_value={"rows": []}), resolve_or_sync_counterparty=create)
    monkeypatch.setattr(registration, "get_moysklad_client", lambda: ms)
    payload = {"email": f"choice-{uuid4().hex[:12]}@example.com", "password": "test-password", "name": "Test", "surname": "Choice",
        "select_program_after_registration": True}
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    uid = response.json()["user_id"]
    try:
        create.assert_not_awaited()
        response = client.post("/api/v1/auth/register/verify", json={"email": payload["email"], "code": "123456"})
        assert response.status_code == 200, response.text
        assert response.json()["user"]["program_selection_required"] is True
        create.assert_not_awaited()
        welcome.assert_not_awaited()
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        response = client.post("/api/v1/auth/registration-program", headers=headers,
            json={"program": program, **({"promo_code": promo} if promo else {})})
        assert response.status_code == 200, response.text
        assert response.json()["program_selection_required"] is False
        assert response.json()["promo_code"] == (promo or "Elixir" if program == "partner" else None)
        assert create.await_args.kwargs["initial_attributes"] == attrs
        with Session(sync_engine) as db:
            profile = db.query(ReferralProfile).filter_by(user_id=uid).one()
            assert profile.reward_program == program
            assert not profile.reward_program_snapshot["registration_sync_pending"]
            assert db.get(User, uid).moysklad_counterparty_id == cid
        retry = client.post("/api/v1/auth/registration-program", headers=headers, json={"program": "bonus"})
        assert retry.status_code == 200
        create.assert_awaited_once()
        welcome.assert_awaited_once()
    finally:
        _delete_user(uid)
