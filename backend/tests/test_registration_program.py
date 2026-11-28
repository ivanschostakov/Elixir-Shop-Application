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
from src.app.services.benefits.settlement_schemas import SettlementRead
from src.database.models import User, ReferralProfile, LoyaltyBonusCredit
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
    monkeypatch.setattr("src.app.services.benefits.settlement.get_account_settlement", AsyncMock(return_value=SettlementRead(status="fresh")))
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


def test_website_profile_cannot_replace_an_unfinished_registration_choice():
    from src.app.services.referrals.bitrix_sync import apply_bitrix_program_profile
    profile = SimpleNamespace(reward_program_selection_source="registration", reward_program="bonus",
        reward_program_snapshot={"registration_selection_required": True})
    user = SimpleNamespace(promo_code=None)
    apply_bitrix_program_profile(profile, user=user, program_profile={"referrer_promo": "OLD", "stored_discount_percent": 20})
    assert profile.reward_program_selection_source == "registration"
    assert user.promo_code is None


def test_new_customer_attributes_use_accounting_bonus_and_zero_discount():
    dictionary, bonus, partner = uuid4(), uuid4(), uuid4()
    def meta(kind, key): return {"href": f"https://example.test/entity/{kind}/{key}", "type": kind}
    rows = [{"id": PROGRAM_ATTRIBUTE_ID, "type": "customentity", "meta": meta("attributemetadata", PROGRAM_ATTRIBUTE_ID),
        "customEntityMeta": meta("customentity", f"{dictionary}/metadata")},
        {"id": DISCOUNT_ATTRIBUTE_ID, "type": "long", "meta": meta("attributemetadata", DISCOUNT_ATTRIBUTE_ID)},
        {"id": REFERRER_ATTRIBUTE_ID, "type": "string", "meta": meta("attributemetadata", REFERRER_ATTRIBUTE_ID)}]
    choices = [{"name": "Бонусная", "meta": meta("customentity", bonus)}, {"name": "Партнерская", "meta": meta("customentity", partner)}]
    client = SimpleNamespace(get_all=AsyncMock(side_effect=[rows, choices]))
    attrs = asyncio.run(registration._initial_attributes(client))
    assert client.get_all.await_args.args == (f"/entity/customentity/{dictionary}",)
    assert attrs[0]["value"]["meta"]["href"].endswith(str(bonus))
    assert attrs[1]["value"] == 0
    assert len(attrs) == 2


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


def test_existing_linked_customer_with_legacy_alert_cannot_be_switched(client, registered_user, monkeypatch):
    uid = registered_user["user_id"]
    with Session(sync_engine) as db:
        profile = db.query(ReferralProfile).filter_by(user_id=uid).one_or_none()
        if profile is None:
            profile = ReferralProfile(user_id=uid)
            db.add(profile)
        profile.reward_program_selection_source = "registration"
        profile.reward_program_snapshot = {"registration_selection_required": True}
        profile.reward_program = "partner"
        user = db.get(User, uid)
        user.moysklad_counterparty_id = uuid4()
        user.promo_code = "EXISTING"
        db.commit()
    provision = AsyncMock(side_effect=AssertionError("Existing program must not be overwritten"))
    monkeypatch.setattr(registration, "_registration_counterparty", provision)
    response = client.get("/api/v1/auth/me", headers=registered_user["headers"])
    assert response.json()["program_selection_required"] is False
    response = client.post("/api/v1/auth/registration-program", headers=registered_user["headers"], json={"program": "bonus"})
    assert response.status_code == 200, response.text
    assert response.json()["program_selection_required"] is False
    assert response.json()["promo_code"] == "EXISTING"
    provision.assert_not_awaited()
    with Session(sync_engine) as db:
        assert db.query(ReferralProfile).filter_by(user_id=uid).one().reward_program == "partner"


@pytest.mark.parametrize("fields,signup_platform,verify_platform,verify_route", [
    ({}, None, "android", "/register/verify"),
    ({}, "ios", None, "/register/verify"),
    ({"select_program_after_registration": True}, None, "android", "/login/verify"),
    ({"reward_program": "partner", "promo_code": "FRIEND"}, None, None, "/register/verify"),
])
def test_new_registration_provisions_bonus_only_after_verification(client, monkeypatch, fields, signup_platform, verify_platform, verify_route):
    from test_orders_api import _delete_user
    from src.app.services.auth.service import sessions
    monkeypatch.setattr(sessions, "_link_moysklad_counterparty_by_email", AsyncMock())
    attrs = [{"value": "metadata checked in separate tests"}]
    monkeypatch.setattr(registration, "_initial_attributes", AsyncMock(return_value=attrs))
    cid = uuid4()
    create = AsyncMock(return_value=SimpleNamespace(counterparty_id=cid, created=True))
    ms = MoySkladClient(token="test", base_url="https://example.test/api")
    monkeypatch.setattr(ms, "get_page", AsyncMock(return_value={"rows": []}))
    monkeypatch.setattr(ms, "resolve_or_sync_counterparty", create)
    monkeypatch.setattr(registration, "get_moysklad_client", lambda: ms)
    payload = {"email": f"choice-{uuid4().hex[:12]}@example.com", "password": "test-password", "name": "Test", "surname": "Choice",
        **fields}
    response = client.post("/api/v1/auth/register", json=payload,
        headers={"X-App-Platform": signup_platform} if signup_platform else {})
    assert response.status_code == 201, response.text
    uid = response.json()["user_id"]
    try:
        create.assert_not_awaited()
        with Session(sync_engine) as db:
            assert not db.query(LoyaltyBonusCredit).filter_by(user_id=uid).count()
            pending = db.query(ReferralProfile).filter_by(user_id=uid).one_or_none()
            assert pending is None or pending.reward_program_selected_at is None
        response = client.post("/api/v1/auth" + verify_route, json={"email": payload["email"], "code": "123456"},
            headers={"X-App-Platform": verify_platform} if verify_platform else {})
        assert response.status_code == 200, response.text
        assert response.json()["user"]["program_selection_required"] is False
        create.assert_awaited_once()
        if verify_platform:
            with Session(sync_engine) as db:
                credit = db.query(LoyaltyBonusCredit).filter_by(user_id=uid).one()
                assert credit.source_kind == "app_welcome" and credit.points == 1000
                assert (credit.expires_at - credit.earned_at).total_seconds() == 5 * 86400
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        response = client.post("/api/v1/auth/registration-program", headers=headers,
            json={"program": "partner", "promo_code": "FRIEND"})
        assert response.status_code == 200, response.text
        assert response.json()["program_selection_required"] is False
        assert response.json()["promo_code"] is None
        assert create.await_args.kwargs["initial_attributes"] == attrs
        with Session(sync_engine) as db:
            profile = db.query(ReferralProfile).filter_by(user_id=uid).one()
            assert profile.reward_program == "bonus"
            assert not profile.reward_program_snapshot["registration_sync_pending"]
            assert db.get(User, uid).moysklad_counterparty_id == cid
        retry = client.post("/api/v1/auth/registration-program", headers=headers, json={"program": "bonus"})
        assert retry.status_code == 200
        create.assert_awaited_once()
        with Session(sync_engine) as db:
            assert db.query(LoyaltyBonusCredit).filter_by(user_id=uid).count() == int(bool(verify_platform))
    finally:
        _delete_user(uid)


@pytest.mark.parametrize("snapshot", [
    {"registration_selection_required": True},
    {"registration_sync_pending": True, "registration_choice": "partner", "registration_promo": "OLD"},
])
def test_legacy_pending_outage_does_not_block_login_and_retries_bonus(client, registered_user, monkeypatch, snapshot):
    from src.app.services.auth.service import sessions

    uid = registered_user["user_id"]
    with Session(sync_engine) as db:
        user = db.get(User, uid)
        email = user.email
        profile = db.query(ReferralProfile).filter_by(user_id=uid).one_or_none() or ReferralProfile(user_id=uid)
        db.add(profile)
        profile.reward_program = "partner"
        profile.reward_program_selection_source = "registration"
        profile.reward_program_snapshot = snapshot
        db.commit()

    cid = uuid4()
    async def remote(user):
        if provision.await_count == 1:
            await asyncio.sleep(60)
        return cid, True
    provision = AsyncMock(side_effect=remote)
    monkeypatch.setattr(registration, "AUTH_PROVISION_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(registration, "_registration_counterparty", provision)
    monkeypatch.setattr(sessions, "_link_moysklad_counterparty_by_email", AsyncMock())
    started = client.post("/api/v1/auth/login", json={"login": email, "password": "test-password"})
    assert started.status_code == 200, started.text
    login = client.post("/api/v1/auth/login/verify", json={"email": email, "code": "123456"})
    assert login.status_code == 200, login.text
    assert login.json()["user"]["program_selection_required"] is False
    with Session(sync_engine) as db:
        profile = db.query(ReferralProfile).filter_by(user_id=uid).one()
        assert profile.reward_program == "bonus"
        assert profile.reward_program_snapshot["registration_sync_pending"]
        assert profile.reward_program_snapshot["registration_promo"] is None
        assert not profile.reward_program_snapshot["registration_selection_required"]
        assert db.get(User, uid).moysklad_counterparty_id is None
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    with Session(sync_engine) as db:
        db.query(User).filter_by(id=uid).with_for_update().one()
        # A concurrent sync owns the row. An auth read must not wait for its remote call.
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
        assert provision.await_count == 1
    for _ in range(2):
        res = client.post("/api/v1/auth/registration-program", headers=headers, json={"program": "partner"})
        assert res.status_code == 200, res.text
    assert provision.await_count == 2
    with Session(sync_engine) as db:
        assert db.get(User, uid).moysklad_counterparty_id == cid
        assert not db.query(ReferralProfile).filter_by(user_id=uid).one().reward_program_snapshot["registration_sync_pending"]


@pytest.mark.parametrize("identity", ["email", "retry_by_phone", "other_phone", "ambiguous_email", "truncated", "malformed"])
def test_registration_identity_check_never_writes_over_an_existing_card(monkeypatch, identity):
    cid = uuid4()
    user = SimpleNamespace(id=5, email="a@example.com", phone_number="+79990000000")
    card = {"id": str(cid), "email": user.email, "phone": user.phone_number}
    rows = [card]
    if identity in {"retry_by_phone", "other_phone"}:
        user.email = None
        if identity == "retry_by_phone":
            card["externalCode"] = registration.build_counterparty_external_code(user_id=user.id)
    elif identity == "ambiguous_email":
        rows.append(dict(card, id=str(uuid4())))
    elif identity == "truncated":
        rows = [card] * 100
    elif identity == "malformed":
        rows = None
    ms = MoySkladClient(token="test", base_url="https://example.test/api")
    monkeypatch.setattr(ms, "get_page", AsyncMock(return_value={"rows": rows}))
    create = AsyncMock()
    monkeypatch.setattr(ms, "resolve_or_sync_counterparty", create)
    monkeypatch.setattr(registration, "get_moysklad_client", lambda: ms)
    if identity in {"email", "retry_by_phone"}:
        assert asyncio.run(registration._registration_counterparty(user)) == (cid, False)
    else:
        with pytest.raises(HTTPException):
            asyncio.run(registration._registration_counterparty(user))
    create.assert_not_awaited()


def test_old_endpoint_cannot_enroll_unmarked_existing_user(client, registered_user, monkeypatch):
    create = AsyncMock()
    monkeypatch.setattr(registration, "_registration_counterparty", create)
    response = client.post("/api/v1/auth/registration-program", headers=registered_user["headers"],
        json={"program": "partner", "promo_code": "INVITE"})
    assert response.status_code == 200, response.text
    assert response.json()["promo_code"] is None
    assert not response.json()["program_selection_required"]
    create.assert_not_awaited()
    with Session(sync_engine) as db:
        assert not db.query(ReferralProfile).filter_by(user_id=registered_user["user_id"]).count()


def test_discovered_card_does_not_apply_local_registration_default(monkeypatch):
    cid = uuid4()
    profile = SimpleNamespace(reward_program="partner", current_discount_percent=Decimal("6"),
        reward_program_selection_source="registration", reward_program_snapshot={"registration_selection_required": True})
    user = SimpleNamespace(id=1, is_verified=True, moysklad_counterparty_id=None, promo_code="EXISTING")
    db = SimpleNamespace(scalar=AsyncMock(return_value=user.id), refresh=AsyncMock(), commit=AsyncMock())
    monkeypatch.setattr(registration, "get_referral_profile_by_user_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(registration, "_registration_counterparty", AsyncMock(return_value=(cid, False)))
    asyncio.run(registration.sync_registration_choice(db, user=user))
    assert user.moysklad_counterparty_id == cid
    assert (profile.reward_program, profile.current_discount_percent, user.promo_code) == ("partner", Decimal("6"), "EXISTING")
    assert not profile.reward_program_snapshot["registration_sync_pending"]
