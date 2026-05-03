import sys
import types
import uuid
from datetime import timedelta
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
from src.integrations.website_identity import website_identity_client
from src.integrations.website_identity.exceptions import WebsiteIdentityError
from src.database.models import User, WebsiteCoupon, WebsiteDiscountEntitlement, WebsiteIdentity

SYNC_DB_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
sync_engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)


def _delete_user(user_id: int) -> None:
    with Session(sync_engine) as session:
        user = session.get(User, user_id)
        if user is None:
            return
        website_identity = session.query(WebsiteIdentity).filter(WebsiteIdentity.user_id == user_id).one_or_none()
        if website_identity is not None:
            session.delete(website_identity)
            session.flush()
        session.delete(user)
        session.commit()


def _get_user(user_id: int) -> User | None:
    with Session(sync_engine) as session:
        user = session.get(User, user_id)
        if user is None:
            return None
        session.expunge(user)
        return user


def _get_website_identity_snapshot(user_id: int) -> dict | None:
    with Session(sync_engine) as session:
        website_identity = session.query(WebsiteIdentity).filter(WebsiteIdentity.user_id == user_id).one_or_none()
        if website_identity is None:
            return None
        coupons = (
            session.query(WebsiteCoupon).filter(WebsiteCoupon.website_identity_id == website_identity.id).order_by(WebsiteCoupon.id).all()
        )
        entitlements = (
            session.query(WebsiteDiscountEntitlement)
            .filter(WebsiteDiscountEntitlement.website_identity_id == website_identity.id)
            .order_by(WebsiteDiscountEntitlement.id)
            .all()
        )
        return {
            "id": website_identity.id,
            "website_user_id": website_identity.website_user_id,
            "last_synced_at": website_identity.last_synced_at,
            "coupon_snapshots": [
                {
                    "id": coupon.id,
                    "coupon_code": coupon.coupon_code,
                    "is_active": coupon.is_active,
                    "use_count": coupon.use_count,
                }
                for coupon in coupons
            ],
            "discount_entitlements": [
                {
                    "id": entitlement.id,
                    "source_name": entitlement.source_name,
                    "is_active": entitlement.is_active,
                }
                for entitlement in entitlements
            ],
        }


@pytest.fixture()
def registered_user(register_verified_user):
    token = uuid.uuid4().hex[:12]
    payload = register_verified_user({
        "username": f"u{token}",
        "email": f"website_identity_{token}@example.com",
        "password": "test-password",
        "name": "Plain",
        "surname": "User",
    })
    user_id = payload["user"]["id"]

    try:
        yield {"user_id": user_id, "headers": {"Authorization": f"Bearer {payload['access_token']}"}}
    finally:
        _delete_user(user_id)


@pytest.fixture()
def anyio_backend():
    return "asyncio"


def _website_payload(*, website_user_id: int, login: str, email: str, name: str = "Site", surname: str = "User") -> dict:
    return {
        "user": {
            "id": website_user_id,
            "login": login,
            "name": name,
            "last_name": surname,
            "second_name": "Middle",
            "email": email,
            "personal_phone": "+79990000001",
            "personal_mobile": "+79990000002",
            "personal_city": "Ufa",
            "date_register": "2026-04-01T12:00:00+05:00",
            "last_login": "2026-04-08T20:15:00+05:00",
            "group_ids": [3, 33],
            "group_names": ["Website Customers", "Заказы больше 100 т. р."],
            "custom_fields": {
                "UF_PROMO": "WELCOME",
                "UF_PARENT_ID": "7",
                "UF_PERCENT": "19",
                "UF_ORDER_SUMM": "3060.33|RUB",
            },
        },
        "discounts": {
            "referral_program": {
                "promo_code": "WELCOME",
                "parent_user_id": 7,
                "percent": 19,
                "order_sum": {"raw": "3060.33|RUB", "amount": 3060.33, "currency": "RUB"},
            },
            "referral_tier": {"group_id": 33, "group_name": "Заказы больше 100 т. р."},
            "bonus_account": {
                "id": website_user_id,
                "user_id": website_user_id,
                "balance": 125.5,
                "currency": "RUB",
                "active": True,
                "date_create": "2026-04-01T12:00:00+05:00",
            },
            "personal_discounts": [
                {
                    "id": 7,
                    "source_kind": "group",
                    "name": "VIP",
                    "discount_type": "percent",
                    "discount_value": 5.0,
                    "currency": "RUB",
                    "priority": 10,
                    "is_stackable": False,
                    "is_active": True,
                }
            ],
            "discount_groups": [{"id": 33, "name": "Заказы больше 100 т. р."}],
            "active_coupons": [
                {
                    "id": website_user_id + 5000,
                    "coupon": "APRIL-10",
                    "max_use": 1,
                    "use_count": 0,
                    "discount": {
                        "id": 901,
                        "name": "April 10%",
                        "discount_type": "percent",
                        "discount_value": 10.0,
                        "value": 10.0,
                        "currency": "RUB",
                    },
                }
            ],
            "recent_used_coupons": [
                {
                    "coupon": "MARCH-5",
                    "discount_id": 902,
                    "discount_name": "March 5",
                    "discount_type": "fixed_amount",
                    "discount_value": 5.0,
                    "currency": "RUB",
                }
            ],
        },
    }


def test_link_my_website_identity_creates_link_and_syncs_user(client: TestClient, registered_user, monkeypatch: pytest.MonkeyPatch):
    website_user_id = 91000 + (uuid.uuid4().int % 1000000)
    website_data = _website_payload(
        website_user_id=website_user_id,
        login="linked-site-user",
        email=f"linked_{uuid.uuid4().hex[:8]}@example.com",
        name="Linked",
        surname="Identity",
    )

    async def fake_authenticate(*, login: str, password: str) -> dict:
        assert login == "site-login"
        assert password == "site-password"
        return website_data

    monkeypatch.setattr(website_identity_client, "authenticate", fake_authenticate)

    response = client.post(
        "/api/v1/users/me/website-identity/link",
        headers=registered_user["headers"],
        json={"login": "site-login", "password": "site-password"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user_id"] == registered_user["user_id"]
    assert payload["website_user_id"] == website_user_id
    assert payload["website_login"] == "linked-site-user"
    assert payload["website_email"] == website_data["user"]["email"]
    assert payload["group_ids"] == [3, 33]
    assert payload["discount_groups"] == [{"id": 33, "name": "Заказы больше 100 т. р."}]
    assert payload["active_coupons"][0]["coupon"] == "APRIL-10"
    assert payload["referral_profile"]["own_promo_code"] == "WELCOME"
    assert payload["referral_profile"]["tier_group_id"] == 33
    assert payload["referral_profile"]["tier_group_name"] == "Заказы больше 100 т. р."
    assert payload["bonus_account_snapshot"]["website_bonus_account_external_id"] == website_user_id
    assert payload["bonus_account_snapshot"]["currency"] == "RUB"
    assert payload["discount_entitlements"][0]["source_name"] == "VIP"
    assert payload["coupon_snapshots"][0]["coupon_code"] == "APRIL-10"
    assert payload["coupon_snapshots"][0]["discount_type"] == "percent"
    assert payload["coupon_snapshots"][0]["discount_value"] == 10.0

    get_response = client.get("/api/v1/users/me/website-identity", headers=registered_user["headers"])
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["website_user_id"] == website_user_id
    assert get_response.json()["referral_profile"]["own_promo_code"] == "WELCOME"

    synced_user = _get_user(registered_user["user_id"])
    assert synced_user is not None
    assert synced_user.email == website_data["user"]["email"]
    assert synced_user.name == "Linked"
    assert synced_user.surname == "Identity"
    assert synced_user.phone_number == "+79990000001"
    assert synced_user.is_verified is True


def test_website_login_creates_local_user_and_identity(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    website_user_id = 91000 + (uuid.uuid4().int % 1000000)
    website_data = _website_payload(
        website_user_id=website_user_id,
        login=f"site-login-{website_user_id}",
        email=f"website_login_{uuid.uuid4().hex[:8]}@example.com",
        name="Fresh",
        surname="Account",
    )

    async def fake_authenticate(*, login: str, password: str) -> dict:
        assert login == "remote-user"
        assert password == "remote-pass"
        return website_data

    monkeypatch.setattr(website_identity_client, "authenticate", fake_authenticate)

    response = client.post("/api/v1/auth/website/login", json={"login": "remote-user", "password": "remote-pass"})

    assert response.status_code == 200, response.text
    payload = response.json()
    user_id = payload["user"]["id"]

    try:
        assert payload["user"]["email"] == website_data["user"]["email"]
        assert payload["user"]["name"] == "Fresh"
        assert payload["user"]["surname"] == "Account"
        assert payload["website_identity"]["user_id"] == user_id
        assert payload["website_identity"]["website_user_id"] == website_user_id
        assert payload["website_identity"]["website_login"] == f"site-login-{website_user_id}"
        assert payload["website_identity"]["bonus_account"]["id"] == website_user_id
        assert payload["website_identity"]["bonus_account"]["currency"] == "RUB"
        assert payload["website_identity"]["bonus_account_snapshot"]["balance"] == 125.5
        assert payload["website_identity"]["bonus_account_snapshot"]["currency"] == "RUB"
        assert payload["website_identity"]["coupon_snapshots"][0]["coupon_code"] == "APRIL-10"
        assert payload["access_token"]
        assert payload["refresh_token"]
        assert payload["session_id"] > 0
    finally:
        _delete_user(user_id)


def test_plain_login_uses_website_identity_first_and_returns_tokens(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    website_user_id = 91000 + (uuid.uuid4().int % 1000000)
    website_data = _website_payload(
        website_user_id=website_user_id,
        login=f"site-login-{website_user_id}",
        email=f"website_login_{uuid.uuid4().hex[:8]}@example.com",
        name="Website",
        surname="First",
    )

    async def fake_authenticate(*, login: str, password: str) -> dict:
        assert login == "remote-user"
        assert password == "remote-pass"
        return website_data

    monkeypatch.setattr(website_identity_client, "authenticate", fake_authenticate)

    response = client.post("/api/v1/auth/login", json={"login": "remote-user", "password": "remote-pass"})

    assert response.status_code == 200, response.text
    payload = response.json()
    user_id = payload["user"]["id"]
    try:
        assert payload["user"]["email"] == website_data["user"]["email"]
        assert payload["user"]["name"] == "Website"
        assert payload["user"]["surname"] == "First"
        assert payload["access_token"]
        assert payload["refresh_token"]
        assert payload["session_id"] > 0

        website_snapshot_response = client.get(
            "/api/v1/users/me/website-identity",
            headers={"Authorization": f"Bearer {payload['access_token']}"},
        )
        assert website_snapshot_response.status_code == 200, website_snapshot_response.text
        assert website_snapshot_response.json()["website_user_id"] == website_user_id
    finally:
        _delete_user(user_id)


def test_plain_login_falls_back_to_local_credentials_when_website_auth_fails(
    client: TestClient,
    register_verified_user,
    monkeypatch: pytest.MonkeyPatch,
):
    token = uuid.uuid4().hex[:12]
    email = f"plain_login_{token}@example.com"
    password = "test-password"
    registration_payload = register_verified_user({
        "username": f"u{token}",
        "email": email,
        "password": password,
        "name": "Plain",
        "surname": "Fallback",
    })
    user_id = registration_payload["user"]["id"]

    async def fake_authenticate(*, login: str, password: str) -> dict:
        raise WebsiteIdentityError("Invalid website credentials", status_code=401, error_code="invalid_credentials")

    monkeypatch.setattr(website_identity_client, "authenticate", fake_authenticate)

    try:
        response = client.post("/api/v1/auth/login", json={"login": email, "password": password})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["verification_required"] is True
        assert payload["email"] == email
    finally:
        _delete_user(user_id)


def test_relink_preserves_snapshot_row_ids_and_marks_missing_rows_inactive(
    client: TestClient, registered_user, monkeypatch: pytest.MonkeyPatch
):
    website_user_id = 91000 + (uuid.uuid4().int % 1000000)
    first_payload = _website_payload(
        website_user_id=website_user_id,
        login="stable-site-user",
        email=f"stable_{uuid.uuid4().hex[:8]}@example.com",
        name="Stable",
        surname="Snapshot",
    )
    first_payload["discounts"]["personal_discounts"] = [
        {
            "id": 7,
            "source_kind": "group",
            "name": "VIP",
            "discount_type": "percent",
            "discount_value": 5.0,
            "currency": "RUB",
            "priority": 10,
            "is_stackable": False,
            "is_active": True,
        }
    ]
    first_payload["discounts"]["active_coupons"] = [
        {
            "id": website_user_id + 100,
            "coupon": "APRIL-10",
            "max_use": 3,
            "use_count": 0,
            "discount": {"id": 901, "name": "April 10%", "discount_type": "percent", "discount_value": 10.0, "value": 10.0},
        }
    ]

    async def fake_authenticate_first(*, login: str, password: str) -> dict:
        assert login == "site-login"
        assert password == "site-password"
        return first_payload

    monkeypatch.setattr(website_identity_client, "authenticate", fake_authenticate_first)

    first_response = client.post(
        "/api/v1/users/me/website-identity/link",
        headers=registered_user["headers"],
        json={"login": "site-login", "password": "site-password"},
    )
    assert first_response.status_code == 200, first_response.text

    first_snapshot = _get_website_identity_snapshot(registered_user["user_id"])
    assert first_snapshot is not None
    first_coupon = next(coupon for coupon in first_snapshot["coupon_snapshots"] if coupon["coupon_code"] == "APRIL-10")
    first_entitlement = next(
        entitlement for entitlement in first_snapshot["discount_entitlements"] if entitlement["source_name"] == "VIP"
    )

    second_payload = _website_payload(
        website_user_id=website_user_id,
        login="stable-site-user",
        email=first_payload["user"]["email"],
        name="Stable",
        surname="Snapshot",
    )
    second_payload["discounts"]["personal_discounts"] = []
    second_payload["discounts"]["active_coupons"] = [
        {
            "id": website_user_id + 100,
            "coupon": "APRIL-10",
            "max_use": 3,
            "use_count": 1,
            "discount": {"id": 901, "name": "April 10%", "discount_type": "percent", "discount_value": 10.0, "value": 10.0},
        }
    ]
    second_payload["discounts"]["recent_used_coupons"] = [
        {
            "id": website_user_id + 101,
            "coupon": "MARCH-5",
            "discount_type": "fixed_amount",
            "discount_id": 902,
            "discount_name": "March 5",
            "discount_value": 5.0,
            "currency": "RUB",
        }
    ]

    async def fake_authenticate_second(*, login: str, password: str) -> dict:
        assert login == "site-login"
        assert password == "site-password"
        return second_payload

    monkeypatch.setattr(website_identity_client, "authenticate", fake_authenticate_second)

    second_response = client.post(
        "/api/v1/users/me/website-identity/link",
        headers=registered_user["headers"],
        json={"login": "site-login", "password": "site-password"},
    )
    assert second_response.status_code == 200, second_response.text

    second_snapshot = _get_website_identity_snapshot(registered_user["user_id"])
    assert second_snapshot is not None
    second_coupon = next(coupon for coupon in second_snapshot["coupon_snapshots"] if coupon["coupon_code"] == "APRIL-10")
    stale_entitlement = next(
        entitlement for entitlement in second_snapshot["discount_entitlements"] if entitlement["source_name"] == "VIP"
    )
    used_coupon = next(coupon for coupon in second_snapshot["coupon_snapshots"] if coupon["coupon_code"] == "MARCH-5")

    assert second_coupon["id"] == first_coupon["id"]
    assert stale_entitlement["id"] == first_entitlement["id"]
    assert stale_entitlement["is_active"] is False
    assert used_coupon["is_active"] is False


def test_link_website_identity_handles_empty_custom_fields_and_defaults_bonus_currency(
    client: TestClient, registered_user, monkeypatch: pytest.MonkeyPatch
):
    website_user_id = 91000 + (uuid.uuid4().int % 1000000)
    website_data = _website_payload(
        website_user_id=website_user_id,
        login="empty-fields-site-user",
        email=f"empty_fields_{uuid.uuid4().hex[:8]}@example.com",
    )
    website_data["user"]["custom_fields"] = []
    website_data["discounts"]["referral_program"] = {"promo_code": "WELCOME"}
    website_data["discounts"]["bonus_account"] = {"id": website_user_id, "balance": 125.5, "active": True}

    async def fake_authenticate(*, login: str, password: str) -> dict:
        assert login == "site-login"
        assert password == "site-password"
        return website_data

    monkeypatch.setattr(website_identity_client, "authenticate", fake_authenticate)

    response = client.post(
        "/api/v1/users/me/website-identity/link",
        headers=registered_user["headers"],
        json={"login": "site-login", "password": "site-password"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["custom_fields"] == {}
    assert payload["referral_profile"]["own_promo_code"] == "WELCOME"
    assert payload["bonus_account_snapshot"]["currency"] == "RUB"


def test_link_website_identity_keeps_referral_tier_informational_without_personal_discount(
    client: TestClient, registered_user, monkeypatch: pytest.MonkeyPatch
):
    website_user_id = 91000 + (uuid.uuid4().int % 1000000)
    website_data = _website_payload(
        website_user_id=website_user_id,
        login="tier-only-site-user",
        email=f"tier_only_{uuid.uuid4().hex[:8]}@example.com",
    )
    website_data["discounts"]["personal_discounts"] = []

    async def fake_authenticate(*, login: str, password: str) -> dict:
        assert login == "site-login"
        assert password == "site-password"
        return website_data

    monkeypatch.setattr(website_identity_client, "authenticate", fake_authenticate)

    response = client.post(
        "/api/v1/users/me/website-identity/link",
        headers=registered_user["headers"],
        json={"login": "site-login", "password": "site-password"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["referral_profile"]["tier_group_id"] == 33
    assert payload["referral_profile"]["tier_group_name"] == "Заказы больше 100 т. р."
    assert payload["discount_entitlements"] == []


def test_link_website_identity_rolls_back_when_relationship_sync_fails(
    client: TestClient, registered_user, monkeypatch: pytest.MonkeyPatch
):
    website_user_id = 91000 + (uuid.uuid4().int % 1000000)
    website_data = _website_payload(
        website_user_id=website_user_id,
        login="rollback-site-user",
        email=f"rollback_{uuid.uuid4().hex[:8]}@example.com",
        name="Broken",
        surname="Sync",
    )

    async def fake_authenticate(*, login: str, password: str) -> dict:
        assert login == "site-login"
        assert password == "site-password"
        return website_data

    async def broken_relationship_sync(*args, **kwargs):
        raise RuntimeError("relationship sync failed")

    monkeypatch.setattr(website_identity_client, "authenticate", fake_authenticate)

    import src.app.services.website_identities.sync as website_identity_sync_module

    monkeypatch.setattr(website_identity_sync_module, "sync_website_identity_relationships", broken_relationship_sync)

    original_user = _get_user(registered_user["user_id"])
    assert original_user is not None

    with pytest.raises(RuntimeError, match="relationship sync failed"):
        client.post(
            "/api/v1/users/me/website-identity/link",
            headers=registered_user["headers"],
            json={"login": "site-login", "password": "site-password"},
        )

    rolled_back_user = _get_user(registered_user["user_id"])
    assert rolled_back_user is not None
    assert rolled_back_user.email == original_user.email
    assert rolled_back_user.name == original_user.name
    assert rolled_back_user.surname == original_user.surname
    assert _get_website_identity_snapshot(registered_user["user_id"]) is None


@pytest.mark.anyio
async def test_sync_identity_batch_updates_last_synced_at_for_missing_remote_identity(monkeypatch: pytest.MonkeyPatch):
    website_user_id = 91000 + (uuid.uuid4().int % 1000000)
    old_last_synced_at = ufa_now() - timedelta(days=2)
    identity = WebsiteIdentity(
        id=1,
        user_id=42,
        website_user_id=website_user_id,
        website_login="sync-site-user",
        group_ids=[],
        group_names=[],
        custom_fields={},
        discount_groups=[],
        active_coupons=[],
        recent_used_coupons=[],
        last_synced_at=old_last_synced_at,
    )

    class FakeSession:
        def __init__(self, tracked_identity: WebsiteIdentity) -> None:
            self.tracked_identity = tracked_identity
            self.added: list[object] = []
            self.commit_count = 0

        async def get(self, model, primary_key):
            if model is WebsiteIdentity and primary_key == self.tracked_identity.id:
                return self.tracked_identity
            return None

        def add(self, obj) -> None:
            self.added.append(obj)

        async def commit(self) -> None:
            self.commit_count += 1

        async def rollback(self) -> None:
            return None

    class FakeSessionContext:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def __aenter__(self) -> FakeSession:
            return self.session

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

    fake_session = FakeSession(identity)

    from src.integrations.bitrix.client import BitrixSyncBatchResult
    from src.scripts import sync_website_identities_from_bitrix_vm as sync_script

    async def fake_fetch_snapshots(user_ids: list[int]) -> BitrixSyncBatchResult:
        assert user_ids == [website_user_id]
        return BitrixSyncBatchResult(snapshots={}, errors={website_user_id: "user_not_found"})

    monkeypatch.setattr(sync_script, "SessionLocal", lambda: FakeSessionContext(fake_session))
    monkeypatch.setattr(sync_script.bitrix_sync_api_client, "fetch_snapshots", fake_fetch_snapshots)

    stats = await sync_script._sync_identity_batch([identity], dry_run=False)

    assert stats.scanned == 1
    assert stats.missing_remote == 1
    assert stats.failed == 0
    assert identity.last_synced_at is not None
    assert identity.last_synced_at > old_last_synced_at
    assert fake_session.commit_count == 1
    assert len(fake_session.added) == 1
    assert fake_session.added[0].status == "missing_remote"
