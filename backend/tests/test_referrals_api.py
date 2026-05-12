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

from config import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER, ufa_now
from src.app.services.referrals.calculations import (
    calculate_commission_amount,
    calculate_level_one_commission_percent,
    calculate_personal_discount_percent,
    calculate_super_referrer_commission_percent,
)
from src.database.models import ReferralProfile, ReferralPromoCode, User

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


def _create_referral_promo(*, user_id: int, code: str, discount_base_total: Decimal = Decimal("100000.00")) -> None:
    with Session(sync_engine) as session:
        profile = session.query(ReferralProfile).filter(ReferralProfile.user_id == user_id).one_or_none()
        if profile is None:
            profile = ReferralProfile(user_id=user_id)
            session.add(profile)
            session.flush()
        profile.initial_purchase_balance = discount_base_total
        profile.referral_discount_base_total = discount_base_total
        profile.current_discount_percent = calculate_personal_discount_percent(discount_base_total, has_referrer=True)
        profile.own_promo_code = code
        profile.own_promo_issued_at = ufa_now()

        session.add(
            ReferralPromoCode(
                owner_user_id=user_id,
                code=code,
                is_active=True,
                source_system="app",
                issued_at=ufa_now(),
            )
        )
        session.commit()


def test_personal_discount_table_requires_foreign_referrer():
    assert calculate_personal_discount_percent("0.00", has_referrer=False) == Decimal("0.00")
    assert calculate_personal_discount_percent("0.00", has_referrer=True) == Decimal("3.00")
    assert calculate_personal_discount_percent("29999.99", has_referrer=True) == Decimal("3.00")
    assert calculate_personal_discount_percent("30000.00", has_referrer=True) == Decimal("3.00")
    assert calculate_personal_discount_percent("40000.00", has_referrer=True) == Decimal("4.00")
    assert calculate_personal_discount_percent("100000.00", has_referrer=True) == Decimal("10.00")
    assert calculate_personal_discount_percent("200000.00", has_referrer=True) == Decimal("20.00")
    assert calculate_personal_discount_percent("999999.00", has_referrer=True) == Decimal("20.00")


def test_commission_rules_include_kiparis_fixed_twenty_percent_and_clamp():
    assert calculate_level_one_commission_percent(
        referrer_discount_percent="20.00",
        referral_discount_percent="3.00",
        promo_code="REGULAR",
    ) == Decimal("17.00")
    assert calculate_commission_amount("10000.00", "17.00") == Decimal("1700.00")
    assert calculate_level_one_commission_percent(
        referrer_discount_percent="20.00",
        referral_discount_percent="20.00",
        promo_code="REGULAR",
    ) == Decimal("3.00")
    assert calculate_level_one_commission_percent(
        referrer_discount_percent="3.00",
        referral_discount_percent="12.00",
        promo_code="REGULAR",
    ) == Decimal("0.00")
    assert calculate_level_one_commission_percent(
        referrer_discount_percent="20.00",
        referral_discount_percent="12.00",
        promo_code="КИПАРИС",
    ) == Decimal("0.00")
    assert calculate_super_referrer_commission_percent() == Decimal("3.00")


def test_referrer_code_attach_and_replacement_confirmation(client: TestClient, registered_user_factory):
    referrer = registered_user_factory(email_prefix="referrer")
    second_referrer = registered_user_factory(email_prefix="referrer")
    buyer = registered_user_factory(email_prefix="buyer")
    code = f"REF{uuid.uuid4().hex[:8]}".upper()
    second_code = f"REF{uuid.uuid4().hex[:8]}".upper()
    _create_referral_promo(user_id=referrer["user_id"], code=code)
    _create_referral_promo(user_id=second_referrer["user_id"], code=second_code)

    check_response = client.post(
        "/api/v1/users/me/referral-profile/referrer-code/check",
        headers=buyer["headers"],
        json={"code": f"  {code.lower()}  "},
    )
    assert check_response.status_code == 200, check_response.text
    check_payload = check_response.json()
    assert check_payload["is_valid"] is True
    assert check_payload["status"] == "available"
    assert check_payload["requires_confirmation"] is False
    assert check_payload["referrer_user_id"] == referrer["user_id"]

    attach_response = client.post(
        "/api/v1/users/me/referral-profile/referrer-code",
        headers=buyer["headers"],
        json={"code": code},
    )
    assert attach_response.status_code == 200, attach_response.text
    attach_payload = attach_response.json()
    assert attach_payload["referrer_promo_code"] == code
    assert _decimal(attach_payload["current_discount_percent"]) == Decimal("3.00")

    replace_check_response = client.post(
        "/api/v1/users/me/referral-profile/referrer-code/check",
        headers=buyer["headers"],
        json={"code": second_code},
    )
    assert replace_check_response.status_code == 200, replace_check_response.text
    replace_check_payload = replace_check_response.json()
    assert replace_check_payload["is_valid"] is True
    assert replace_check_payload["requires_confirmation"] is True
    assert replace_check_payload["warning"]

    unconfirmed_replace_response = client.post(
        "/api/v1/users/me/referral-profile/referrer-code",
        headers=buyer["headers"],
        json={"code": second_code},
    )
    assert unconfirmed_replace_response.status_code == 409, unconfirmed_replace_response.text

    confirmed_replace_response = client.post(
        "/api/v1/users/me/referral-profile/referrer-code",
        headers=buyer["headers"],
        json={"code": second_code, "confirmed": True},
    )
    assert confirmed_replace_response.status_code == 200, confirmed_replace_response.text
    confirmed_payload = confirmed_replace_response.json()
    assert confirmed_payload["referrer_promo_code"] == second_code
    assert _decimal(confirmed_payload["current_discount_percent"]) == Decimal("3.00")

    detach_response = client.delete(
        "/api/v1/users/me/referral-profile/referrer-code",
        headers=buyer["headers"],
    )
    assert detach_response.status_code == 200, detach_response.text
    detach_payload = detach_response.json()
    assert detach_payload["referrer_promo_code"] is None
    assert _decimal(detach_payload["current_discount_percent"]) == Decimal("0.00")


def test_referrer_code_rejects_own_promo(client: TestClient, registered_user_factory):
    buyer = registered_user_factory(email_prefix="buyer")
    own_code = f"OWN{uuid.uuid4().hex[:8]}".upper()
    _create_referral_promo(user_id=buyer["user_id"], code=own_code)

    check_response = client.post(
        "/api/v1/users/me/referral-profile/referrer-code/check",
        headers=buyer["headers"],
        json={"code": own_code},
    )
    assert check_response.status_code == 200, check_response.text
    check_payload = check_response.json()
    assert check_payload["is_valid"] is False
    assert check_payload["status"] == "own_code"

    attach_response = client.post(
        "/api/v1/users/me/referral-profile/referrer-code",
        headers=buyer["headers"],
        json={"code": own_code},
    )
    assert attach_response.status_code == 400, attach_response.text


def test_referral_profile_get_is_idempotent(client: TestClient, registered_user_factory):
    buyer = registered_user_factory(email_prefix="buyer")

    first_response = client.get(
        "/api/v1/users/me/referral-profile",
        headers=buyer["headers"],
    )
    assert first_response.status_code == 200, first_response.text

    second_response = client.get(
        "/api/v1/users/me/referral-profile",
        headers=buyer["headers"],
    )
    assert second_response.status_code == 200, second_response.text

    with Session(sync_engine) as session:
        profile_count = session.query(ReferralProfile).filter(ReferralProfile.user_id == buyer["user_id"]).count()
        assert profile_count == 1
