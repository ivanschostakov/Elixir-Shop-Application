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


def _set_reward_program(user_id: int, program: str) -> None:
    with Session(sync_engine) as session:
        profile = (
            session.query(ReferralProfile)
            .filter(ReferralProfile.user_id == user_id)
            .one_or_none()
        )
        if profile is None:
            profile = ReferralProfile(user_id=user_id)
            session.add(profile)
        profile.reward_program = program
        session.commit()


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


def test_personal_discount_table_is_independent_from_partner_promo():
    assert calculate_personal_discount_percent("0.00", has_promo_code=False) == Decimal("0.00")
    assert calculate_personal_discount_percent("0.00", has_promo_code=True) == Decimal("0.00")
    assert calculate_personal_discount_percent("29999.99", has_promo_code=True) == Decimal("0.00")
    assert calculate_personal_discount_percent("30000.00", has_promo_code=True) == Decimal("3.00")
    assert calculate_personal_discount_percent("40000.00", has_promo_code=True) == Decimal("4.00")
    assert calculate_personal_discount_percent("100000.00", has_promo_code=True) == Decimal("10.00")
    assert calculate_personal_discount_percent("170000.00", has_promo_code=True) == Decimal("17.00")
    assert calculate_personal_discount_percent("200000.00", has_promo_code=False) == Decimal("20.00")
    assert calculate_personal_discount_percent("999999.00", has_promo_code=True) == Decimal("20.00")


def test_referrer_code_requires_partner_program_and_then_uses_configured_source(client: TestClient, registered_user_factory):
    buyer = registered_user_factory(email_prefix="buyer")
    code = f"REF{uuid.uuid4().hex[:8]}".upper()

    check_response = client.post(
        "/api/v1/users/me/referral-profile/referrer-code/check",
        headers=buyer["headers"],
        json={"code": f"  {code.lower()}  "},
    )
    assert check_response.status_code == 409, check_response.text

    _set_reward_program(buyer["user_id"], "partner")
    check_response = client.post(
        "/api/v1/users/me/referral-profile/referrer-code/check",
        headers=buyer["headers"],
        json={"code": f"  {code.lower()}  "},
    )
    assert check_response.status_code == 200, check_response.text
    check_payload = check_response.json()
    assert check_payload["code"] == code
    assert check_payload["is_valid"] is False
    assert check_payload["status"] == "not_configured"

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
    assert _decimal(first_response.json()["current_discount_percent"]) == Decimal("0.00")

    second_response = client.get(
        "/api/v1/users/me/referral-profile",
        headers=buyer["headers"],
    )
    assert second_response.status_code == 200, second_response.text

    with Session(sync_engine) as session:
        profile_count = session.query(ReferralProfile).filter(ReferralProfile.user_id == buyer["user_id"]).count()
        assert profile_count == 1


def test_bonus_program_selection_is_persisted_and_locked(
    client: TestClient,
    registered_user_factory,
    monkeypatch,
):
    async def no_website_profile(_user):
        return None

    monkeypatch.setattr(
        "src.app.services.referrals.program._load_bitrix_program_profile",
        no_website_profile,
    )
    buyer = registered_user_factory(email_prefix="bonus-program")

    selected = client.post(
        "/api/v1/users/me/referral-profile/program",
        headers=buyer["headers"],
        json={"program": "bonus"},
    )
    assert selected.status_code == 200, selected.text
    payload = selected.json()
    assert payload["reward_program"] == "bonus"
    assert payload["program_selection_required"] is False
    assert payload["promo_code"] is None

    locked = client.post(
        "/api/v1/users/me/referral-profile/program",
        headers=buyer["headers"],
        json={"program": "partner"},
    )
    assert locked.status_code == 409, locked.text

    with Session(sync_engine) as session:
        events = (
            session.query(RewardProgramSelectionEvent)
            .filter(RewardProgramSelectionEvent.user_id == buyer["user_id"])
            .all()
        )
        assert len(events) == 1
        assert events[0].selected_program == "bonus"
        assert events[0].source == "user"
