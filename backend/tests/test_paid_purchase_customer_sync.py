import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.app.services.referrals.paid_orders import remote
from src.integrations.bitrix_promo import BitrixPromoError


def missing_customer():
    return BitrixPromoError(status_code=404, code="user_not_found", message="Missing customer")


@pytest.fixture
def scenario(monkeypatch):
    monkeypatch.setattr(remote, "_apply_remote_purchase_progress", AsyncMock())
    monkeypatch.setattr(remote, "refresh_program_profile_from_bitrix", AsyncMock())
    db = SimpleNamespace(commit=AsyncMock())
    user = SimpleNamespace(id=7, email="customer@example.test", name="Test", surname="Customer", is_verified=True)
    purchase = SimpleNamespace(id=6, status="posted", bitrix_sync_status="failed",
        external_order_id="EP-PAID-ONCE", promo_code="REFERRER", amount=Decimal("1234.56"),
        currency="RUB", paid_at=datetime.now(timezone.utc), calculation_snapshot={"buyer_discount_percent": "3"},
        accruals=[], bitrix_buyer_user_id=None)
    client = SimpleNamespace(ensure_customer=AsyncMock(return_value={"user_id": 99}),
        record_paid_purchase=AsyncMock(side_effect=[missing_customer(), {"outcome": "already_recorded", "purchase": {"id": 15, "user_id": 99}}]))
    return db, purchase, user, client


def test_verified_app_customer_is_created_once_and_purchase_keeps_original_idempotency_key(scenario):
    db, purchase, user, client = scenario
    result = asyncio.run(remote._sync_purchase_progress_to_bitrix(db, purchase=purchase, user=user, client=client))
    assert result["outcome"] == "already_recorded"
    assert purchase.bitrix_sync_status == "synced" and purchase.bitrix_purchase_id == 15
    assert purchase.bitrix_buyer_user_id == 99
    client.ensure_customer.assert_awaited_once_with(app_user_id=7, user_email=user.email, name="Test", surname="Customer")
    first, second = client.record_paid_purchase.await_args_list
    assert first.kwargs == second.kwargs and second.kwargs["external_order_id"] == "EP-PAID-ONCE"
    asyncio.run(remote._sync_purchase_progress_to_bitrix(db, purchase=purchase, user=user, client=client))
    assert client.record_paid_purchase.await_count == 2
    client.ensure_customer.assert_awaited_once()


def test_unverified_email_cannot_provision_a_site_customer(scenario):
    db, purchase, user, client = scenario
    user.is_verified = False
    with pytest.raises(BitrixPromoError):
        asyncio.run(remote._sync_purchase_progress_to_bitrix(db, purchase=purchase, user=user, client=client))
    client.ensure_customer.assert_not_awaited()
    assert purchase.bitrix_sync_status == "failed"


def test_failed_customer_sync_leaves_the_same_purchase_retryable(scenario):
    db, purchase, user, client = scenario
    client.ensure_customer.side_effect = BitrixPromoError(status_code=409, code="customer_identity_ambiguous", message="Ambiguous")
    with pytest.raises(BitrixPromoError):
        asyncio.run(remote._sync_purchase_progress_to_bitrix(db, purchase=purchase, user=user, client=client))
    assert purchase.bitrix_sync_status == "failed"
    assert purchase.sync_error.startswith("customer_identity_ambiguous:")
    client.record_paid_purchase.assert_awaited_once()
