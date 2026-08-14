import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from decimal import Decimal

from src.app.services.referrals.paid_orders import (
    _create_local_accrual_from_bitrix,
    _paid_order_promo,
    _paid_order_promo_discount_percent,
    _period_bounds,
    _rewardable_order_amount,
    _sync_partner_reversal_to_bitrix,
)
from src.integrations.bitrix_promo import BitrixPromoError


def test_paid_order_promo_uses_only_applied_checkout_promo() -> None:
    order = SimpleNamespace(
        checkout_snapshot={
            "benefits": {
                "promo_code": "ENTERED-BUT-NOT-APPLIED",
                "applications": [
                    {
                        "kind": "promo",
                        "code": "APPLIED-REFERRER",
                    }
                ],
            }
        }
    )

    assert _paid_order_promo(order) == "APPLIED-REFERRER"


def test_paid_order_promo_ignores_unapplied_entered_code() -> None:
    order = SimpleNamespace(
        checkout_snapshot={
            "benefits": {
                "promo_code": "INVALID-OR-OWN-CODE",
                "applications": [],
            }
        }
    )

    assert _paid_order_promo(order) is None


def test_paid_order_uses_the_discount_percent_actually_applied_by_the_app() -> None:
    order = SimpleNamespace(
        checkout_snapshot={
            "benefits": {
                "applications": [
                    {
                        "code": "REFERRER",
                        "discount_percent": "3.00",
                    }
                ],
            }
        }
    )

    assert _paid_order_promo_discount_percent(
        order,
        promo="referrer",
    ) == Decimal("3.00")


def test_period_bounds_handle_year_boundary() -> None:
    paid_at = datetime(2026, 12, 31, 22, 10, tzinfo=timezone.utc)

    assert _period_bounds(paid_at) == (
        datetime(2026, 12, 1).date(),
        datetime(2027, 1, 1).date(),
    )


def test_rewardable_order_amount_excludes_delivery_and_uses_paid_merchandise_total() -> None:
    order = SimpleNamespace(
        id=17,
        checkout_snapshot={"benefits": {"total_after_discounts": 5250}},
        grand_total=Decimal("7190.00"),
        delivery_total=Decimal("1940.00"),
    )

    assert _rewardable_order_amount(order) == Decimal("5250")


def test_rewardable_order_amount_uses_legacy_total_without_delivery() -> None:
    order = SimpleNamespace(
        id=18,
        checkout_snapshot={},
        grand_total=Decimal("7450.00"),
        delivery_total=Decimal("1940.00"),
    )

    assert _rewardable_order_amount(order) == Decimal("5510.00")


def test_remote_accrual_keeps_beneficiary_email_without_app_profile() -> None:
    class EmptyScalarResult:
        @staticmethod
        def scalar_one_or_none():
            return None

    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[EmptyScalarResult(), EmptyScalarResult()]
        ),
        add=Mock(),
    )
    purchase = SimpleNamespace(id=77, currency="RUB")

    row = asyncio.run(
        _create_local_accrual_from_bitrix(
            db,
            purchase=purchase,
            raw_accrual={
                "id": 811,
                "beneficiary_user_id": 396,
                "beneficiary": {
                    "user_id": 396,
                    "email": "referrer@example.com",
                    "name": "Website Referrer",
                },
                "referral_user_id": 512,
                "level": 1,
                "amount": "340.50",
                "currency": "RUB",
                "status": "approved",
            },
        )
    )

    assert row is not None
    assert row.beneficiary_user_id is None
    assert row.beneficiary_bitrix_user_id == 396
    assert row.beneficiary_email == "referrer@example.com"
    assert row.beneficiary_name == "Website Referrer"
    db.add.assert_called_once_with(row)


def test_partner_reversal_is_idempotently_completed_in_local_mirror() -> None:
    accrual = SimpleNamespace(status="pending", reason=None)
    purchase = SimpleNamespace(
        external_order_id="EP-TEST-REVERSAL",
        status="reversal_pending",
        reversed_at=None,
        bitrix_sync_status="pending",
        bitrix_synced_at=None,
        sync_error=None,
        accruals=[accrual],
    )
    client = SimpleNamespace(
        reverse_paid_purchase=AsyncMock(return_value={"outcome": "already_reversed"})
    )
    db = SimpleNamespace(commit=AsyncMock())

    result = asyncio.run(
        _sync_partner_reversal_to_bitrix(
            db,
            purchase=purchase,
            client=client,
        )
    )

    assert result["outcome"] == "already_reversed"
    assert purchase.status == "reversed"
    assert purchase.bitrix_sync_status == "synced"
    assert purchase.reversed_at is not None
    assert accrual.status == "rejected"
    assert accrual.reason == "order_reversed"
    db.commit.assert_awaited_once()


def test_missing_remote_purchase_finishes_local_reversal_without_retry_loop() -> None:
    purchase = SimpleNamespace(
        external_order_id="EP-NOT-RECORDED",
        status="reversal_pending",
        reversed_at=None,
        bitrix_sync_status="pending",
        bitrix_synced_at=None,
        sync_error=None,
        accruals=[],
    )
    client = SimpleNamespace(
        reverse_paid_purchase=AsyncMock(
            side_effect=BitrixPromoError(
                status_code=404,
                code="purchase_not_found",
                message="not found",
            )
        )
    )
    db = SimpleNamespace(commit=AsyncMock())

    result = asyncio.run(
        _sync_partner_reversal_to_bitrix(
            db,
            purchase=purchase,
            client=client,
        )
    )

    assert result["outcome"] == "remote_purchase_not_found"
    assert purchase.status == "reversed"
    assert purchase.bitrix_sync_status == "synced"
    assert purchase.sync_error is None
