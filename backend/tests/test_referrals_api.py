import sys
import types
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if "PIL" not in sys.modules:
    pil_module = types.ModuleType("PIL")
    pil_module.Image = types.SimpleNamespace(open=None)

    class _UnidentifiedImageError(Exception):
        pass

    pil_module.UnidentifiedImageError = _UnidentifiedImageError
    sys.modules["PIL"] = pil_module

from config import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER
from src.app.services.referrals.calculations import calculate_personal_discount_percent
from src.database.models import ReferralProfile, RewardProgramSelectionEvent, User

SYNC_DB_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
sync_engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)


def _decimal(value) -> Decimal:
    return Decimal(str(value))


def _delete_user(user_id: int) -> None:
    with Session(sync_engine) as session:
        user = session.get(User, user_id)
        if user is None:
            return
        session.delete(user)
        session.commit()


def _user_promo_code(user_id: int) -> str | None:
    with Session(sync_engine) as session:
        user = session.get(User, user_id)
        return user.promo_code if user is not None else None


def _set_user_promo_code(user_id: int, promo_code: str | None) -> None:
    with Session(sync_engine) as session:
        user = session.get(User, user_id)
        assert user is not None
        user.promo_code = promo_code
        session.commit()


@pytest.fixture(autouse=True)
def disable_bitrix_promo_for_local_referral_tests(monkeypatch):
    monkeypatch.setattr(
        "src.app.services.referrals.promo.bitrix_promo_configured",
        lambda: False,
    )
    monkeypatch.setattr(
        "src.app.services.referrals.bitrix_sync.bitrix_promo_configured",
        lambda: False,
    )
    monkeypatch.setattr(
        "src.app.services.referrals.summary.bitrix_promo_configured",
        lambda: False,
    )


@pytest.fixture()
def registered_user_factory(register_verified_user):
    created_user_ids: list[int] = []

    def _factory(*, email_prefix: str = "referrals") -> dict:
        token = uuid.uuid4().hex[:12]
        payload = register_verified_user({
            "username": f"u{token}",
            "email": f"{email_prefix}_{token}@example.com",
            "password": "test-password",
            "name": "Referral",
            "surname": "Tester",
        })
        created_user_ids.append(payload["user"]["id"])
        return {"user_id": payload["user"]["id"], "headers": {"Authorization": f"Bearer {payload['access_token']}"}}

    try:
        yield _factory
    finally:
        for user_id in reversed(created_user_ids):
            _delete_user(user_id)


def test_personal_discount_requires_program_promo():
    assert calculate_personal_discount_percent("0.00", has_promo_code=False) == Decimal("0.00")
    assert calculate_personal_discount_percent("0.00", has_promo_code=True) == Decimal("3.00")
    assert calculate_personal_discount_percent("29999.99", has_promo_code=True) == Decimal("3.00")
    assert calculate_personal_discount_percent("30000.00", has_promo_code=True) == Decimal("3.00")
    assert calculate_personal_discount_percent("40000.00", has_promo_code=True) == Decimal("4.00")
    assert calculate_personal_discount_percent("100000.00", has_promo_code=True) == Decimal("10.00")
    assert calculate_personal_discount_percent("170000.00", has_promo_code=True) == Decimal("17.00")
    assert calculate_personal_discount_percent("200000.00", has_promo_code=False) == Decimal("0.00")
    assert calculate_personal_discount_percent("999999.00", has_promo_code=True) == Decimal("20.00")


@pytest.mark.parametrize("scenario,expected", [
    ("ok", 204), ("retry", 204), ("timeout_after_write", 204), ("declined", 422),
    ("changed", 409), ("partial_shipment", 409), ("own_program", 409), ("disabled", 409),
    ("unverified_write", 503), ("incomplete_list", 503),
])
def test_accounting_unlink(client, registered_user_factory, monkeypatch, scenario, expected):
    from copy import deepcopy
    from unittest.mock import AsyncMock
    from src.app.services.referrals import unlink as svc
    buyer = registered_user_factory()
    cid = uuid.uuid4()
    with Session(sync_engine) as session:
        user = session.get(User, buyer["user_id"])
        user.promo_code = "OLD"
        user.moysklad_counterparty_id = cid
        session.commit()
    def attr(key, value):
        return {"id": key, "meta": {"href": "https://ms.test/" + key}, "value": value}
    ref = attr(svc.REFERRER_ATTRIBUTE_ID, "Other" if scenario == "changed" else "Old")
    discount = attr(svc.DISCOUNT_ATTRIBUTE_ID, {"name": "12"})
    own = attr(svc.OWN_PROMO_ATTRIBUTE_ID, "MINE" if scenario == "own_program" else None)
    card = {"id": str(cid), "updated": "rev1", "attributes": [
        ref, discount, own, attr(svc.PROGRAM_ATTRIBUTE_ID, {"name": "Партнерская"})]}
    rows = [{"id": str(uuid.uuid4()), "name": "partial", "agent": {"id": str(cid)},
             "sum": 10000, "shippedSum": 5000}] if scenario == "partial_shipment" else []
    async def update(entity, target, patch):
        assert (entity, target) == ("counterparty", cid)
        assert patch == {"attributes": [{"meta": ref["meta"], "value": None},
            {"meta": discount["meta"], "value": {"meta": {"href": "zero"}}}]}
        if scenario != "unverified_write":
            ref["value"], discount["value"], card["updated"] = None, {"name": "0"}, "rev2"
        if scenario == "timeout_after_write":
            raise RuntimeError("lost PUT response")
    ms = types.SimpleNamespace(get_counterparty=AsyncMock(side_effect=lambda _: deepcopy(card)),
        entity_href=lambda *_: "test", get_page=AsyncMock(return_value={"rows": rows,
        "meta": {"size": 3 if scenario == "incomplete_list" else len(rows)}}), _update_entity=AsyncMock(side_effect=update))
    monkeypatch.setattr(svc, "get_moysklad_client", lambda: ms)
    monkeypatch.setattr(svc, "LOYALTY_USE_SETTLEMENT_BALANCE", scenario != "disabled")
    monkeypatch.setattr(svc, "invalidate_account_settlement", AsyncMock())
    monkeypatch.setattr(svc, "zero_discount_attribute", AsyncMock(return_value={"meta": discount["meta"], "value": {"meta": {"href": "zero"}}}))
    body = {"code": "old", "confirm_loss": scenario != "declined", "operation_id": str(uuid.uuid4())}
    def send():
        return client.post("/api/v1/users/me/referral-profile/referrer-code/unlink", headers=buyer["headers"], json=body)
    result = send()
    if scenario == "timeout_after_write":
        assert result.status_code == 503
        body["operation_id"] = str(uuid.uuid4())
        result = send()
    assert result.status_code == expected, result.text
    if scenario == "retry":
        assert send().status_code == 204
        ref["value"] = "Old"
        assert send().status_code == 409  # old request cannot detach a later relationship
    assert ms._update_entity.await_count == int(expected == 204 or scenario == "unverified_write")
    assert _user_promo_code(buyer["user_id"]) == (None if expected == 204 else "OLD")


def test_referrer_code_endpoint_is_available_before_program_selection(
    client: TestClient,
    registered_user_factory,
):
    buyer = registered_user_factory(email_prefix="buyer")
    code = f"REF{uuid.uuid4().hex[:8]}".upper()

    check_response = client.post(
        "/api/v1/users/me/referral-profile/referrer-code/check",
        headers=buyer["headers"],
        json={"code": f"  {code.lower()}  "},
    )
    assert check_response.status_code == 200, check_response.text
    assert check_response.json()["status"] == "not_configured"

    attach_response = client.post(
        "/api/v1/users/me/referral-profile/referrer-code",
        headers=buyer["headers"],
        json={"code": code},
    )
    assert attach_response.status_code == 400, attach_response.text
    assert _user_promo_code(buyer["user_id"]) is None


def test_referral_profile_get_is_idempotent(client: TestClient, registered_user_factory):
    buyer = registered_user_factory(email_prefix="buyer")

    first_response = client.get(
        "/api/v1/users/me/referral-profile",
        headers=buyer["headers"],
    )
    assert first_response.status_code == 200, first_response.text
    first_payload = first_response.json()
    assert _decimal(first_payload["current_discount_percent"]) == Decimal("0.00")
    assert first_payload["reward_program"] == "bonus"
    assert first_payload["program_selection_required"] is False
    assert first_payload["bonus_program_enabled"] is True
    assert _decimal(first_payload["bonus_cashback_percent"]) == Decimal("5.00")
    assert first_payload["partner_program_status"] == "locked"

    second_response = client.get(
        "/api/v1/users/me/referral-profile",
        headers=buyer["headers"],
    )
    assert second_response.status_code == 200, second_response.text

    with Session(sync_engine) as session:
        profile_count = session.query(ReferralProfile).filter(ReferralProfile.user_id == buyer["user_id"]).count()
        assert profile_count == 1


def test_existing_website_promo_activates_partner_program_automatically(
    client: TestClient,
    registered_user_factory,
):
    buyer = registered_user_factory(email_prefix="existing-promo")

    initial = client.get(
        "/api/v1/users/me/referral-profile",
        headers=buyer["headers"],
    )
    assert initial.status_code == 200, initial.text
    assert initial.json()["reward_program"] == "bonus"

    _set_user_promo_code(buyer["user_id"], "EXISTING-PROMO")

    deferred = client.get(
        "/api/v1/users/me/referral-profile",
        headers=buyer["headers"],
    )
    assert deferred.status_code == 200, deferred.text
    deferred_payload = deferred.json()
    assert deferred_payload["reward_program"] == "partner"
    assert deferred_payload["promo_code"] == "EXISTING-PROMO"
    assert _decimal(deferred_payload["current_discount_percent"]) == Decimal("3.00")
    assert deferred_payload["program_selection_required"] is False
    assert deferred_payload["bonus_program_enabled"] is False
    assert _user_promo_code(buyer["user_id"]) == "EXISTING-PROMO"

    blocked = client.post(
        "/api/v1/users/me/referral-profile/referrer-code",
        headers=buyer["headers"],
        json={"code": "ANOTHER-PROMO", "confirmed": True},
    )
    assert blocked.status_code == 409, blocked.text
    assert "Сначала отвяжите текущий промокод" in blocked.json()["detail"]
    assert _user_promo_code(buyer["user_id"]) == "EXISTING-PROMO"

    with Session(sync_engine) as session:
        profile = session.query(ReferralProfile).filter(ReferralProfile.user_id == buyer["user_id"]).one()
        profile.referral_discount_base_total = Decimal("30000.00")
        session.commit()

    selected = client.post(
        "/api/v1/users/me/referral-profile/program",
        headers=buyer["headers"],
        json={"program": "partner"},
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["reward_program"] == "partner"
    assert selected.json()["promo_code"] == "EXISTING-PROMO"

    detached = client.delete(
        "/api/v1/users/me/referral-profile/referrer-code",
        headers=buyer["headers"],
    )
    assert detached.status_code == 200, detached.text
    assert detached.json()["promo_code"] is None
    assert detached.json()["reward_program"] == "bonus"
    assert detached.json()["bonus_program_enabled"] is True


def test_bonus_program_requires_unlinking_existing_promo(
    client: TestClient,
    registered_user_factory,
):
    buyer = registered_user_factory(email_prefix="existing-promo-bonus")
    _set_user_promo_code(buyer["user_id"], "EXISTING-PROMO")

    client.get(
        "/api/v1/users/me/referral-profile",
        headers=buyer["headers"],
    )
    with Session(sync_engine) as session:
        profile = session.query(ReferralProfile).filter(ReferralProfile.user_id == buyer["user_id"]).one()
        profile.referral_discount_base_total = Decimal("30000.00")
        session.commit()

    selected = client.post(
        "/api/v1/users/me/referral-profile/program",
        headers=buyer["headers"],
        json={"program": "bonus"},
    )

    assert selected.status_code == 409, selected.text
    assert "сначала отвяжите промокод" in selected.json()["detail"]
    assert _user_promo_code(buyer["user_id"]) == "EXISTING-PROMO"


def test_partner_program_requires_promo_even_after_30000(
    client: TestClient,
    registered_user_factory,
):
    buyer = registered_user_factory(email_prefix="unified-program")
    profile_response = client.get(
        "/api/v1/users/me/referral-profile", headers=buyer["headers"]
    )
    assert profile_response.status_code == 200, profile_response.text

    before_threshold = client.post(
        "/api/v1/users/me/referral-profile/program",
        headers=buyer["headers"],
        json={"program": "partner"},
    )
    assert before_threshold.status_code == 409, before_threshold.text

    with Session(sync_engine) as session:
        profile = session.query(ReferralProfile).filter(ReferralProfile.user_id == buyer["user_id"]).one()
        profile.referral_discount_base_total = Decimal("30000.00")
        session.commit()

    still_blocked = client.post(
        "/api/v1/users/me/referral-profile/program",
        headers=buyer["headers"],
        json={"program": "partner"},
    )
    assert still_blocked.status_code == 409, still_blocked.text

    cashback = client.post(
        "/api/v1/users/me/referral-profile/program",
        headers=buyer["headers"],
        json={"program": "bonus"},
    )
    assert cashback.status_code == 200, cashback.text
    assert cashback.json()["reward_program"] == "bonus"

    with Session(sync_engine) as session:
        events = (
            session.query(RewardProgramSelectionEvent)
            .filter(RewardProgramSelectionEvent.user_id == buyer["user_id"])
            .all()
        )
        assert events == []
