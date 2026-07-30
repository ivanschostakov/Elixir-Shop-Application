from decimal import Decimal

from src.app.services.benefits.moysklad_bonus import (
    bonus_points_to_rubles,
    bonus_spend_for_subtotal,
    bonus_wallet_from_counterparty,
)
from src.app.services.benefits.redemption import _failed_checkout_snapshot


COUNTERPARTY_ID = "12345678-1234-1234-1234-123456789012"
PROGRAM_ID = "87654321-4321-4321-4321-210987654321"


def test_bonus_wallet_converts_points_and_sales_amount_from_moysklad():
    wallet = bonus_wallet_from_counterparty(
        {
            "id": COUNTERPARTY_ID,
            "bonusPoints": 70,
            "salesAmount": 123456,
            "bonusProgram": {
                "id": PROGRAM_ID,
                "name": "Постоянный клиент",
                "active": True,
                "spendRatePointsToRouble": 2,
                "maxPaidRatePercents": 30,
            },
        }
    )

    assert wallet.balance_points == 70
    assert wallet.balance_rubles == Decimal("35.00")
    assert wallet.sales_amount_rubles == Decimal("1234.56")
    assert wallet.spend_rate_points_to_ruble == 2
    assert wallet.max_paid_rate_percent == Decimal("30")
    assert wallet.is_available is True


def test_bonus_spend_respects_program_percentage_and_whole_points():
    wallet = bonus_wallet_from_counterparty(
        {
            "id": COUNTERPARTY_ID,
            "bonusPoints": 1000,
            "bonusProgram": {
                "id": PROGRAM_ID,
                "active": True,
                "spendRatePointsToRouble": 3,
                "maxPaidRatePercents": 25,
            },
        }
    )

    points, rubles = bonus_spend_for_subtotal(wallet, Decimal("199.95"))

    assert points == 149
    assert rubles == Decimal("49.67")
    assert rubles <= Decimal("50.00")


def test_inactive_bonus_program_cannot_be_spent():
    wallet = bonus_wallet_from_counterparty(
        {
            "id": COUNTERPARTY_ID,
            "bonusPoints": 70,
            "bonusProgram": {
                "id": PROGRAM_ID,
                "active": False,
                "spendRatePointsToRouble": 1,
                "maxPaidRatePercents": 100,
            },
        }
    )

    assert bonus_points_to_rubles(70, 1) == Decimal("70.00")
    assert wallet.is_available is False
    assert bonus_spend_for_subtotal(wallet, Decimal("100.00")) == (0, Decimal("0.00"))


def test_failed_redemption_restores_total_and_removes_only_bonus_application():
    snapshot = _failed_checkout_snapshot(
        {
            "benefits": {
                "stacked_discount_amount": 30,
                "total_after_discounts": 70,
                "use_bonus_rubles": True,
                "bonus_applied_points": 20,
                "bonus_applied_rubles": 20,
                "applications": [
                    {"source_kind": "app_referral", "discount_amount": "10.00"},
                    {"source_kind": "moysklad_bonus", "discount_amount": "20.00"},
                ],
            }
        },
        restored_amount=Decimal("20.00"),
        error="balance changed",
    )

    assert snapshot["benefits"]["stacked_discount_amount"] == 10.0
    assert snapshot["benefits"]["total_after_discounts"] == 90.0
    assert snapshot["benefits"]["applications"] == [
        {"source_kind": "app_referral", "discount_amount": "10.00"}
    ]
    assert snapshot["benefits"]["use_bonus_rubles"] is False
