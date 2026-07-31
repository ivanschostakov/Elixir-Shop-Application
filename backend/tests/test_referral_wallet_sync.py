import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

from src.app.services.referrals.wallet_sync import (
    bonus_points_for_rubles,
    sync_referral_accrual_to_bonus_wallet,
)


COUNTERPARTY_ID = UUID("12345678-1234-1234-1234-123456789012")
PROGRAM_ID = UUID("87654321-4321-4321-4321-210987654321")
EARNING_ID = UUID("11111111-2222-3333-4444-555555555555")
REVERSAL_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


def _approved_accrual() -> SimpleNamespace:
    return SimpleNamespace(
        id=81,
        beneficiary_user_id=19,
        beneficiary_email="buyer@example.com",
        status="approved",
        currency="RUB",
        commission_amount=Decimal("123.45"),
        level=1,
        purchase=SimpleNamespace(external_order_id="EP-WALLET1"),
        wallet_sync_status="pending",
        moysklad_counterparty_id=None,
        moysklad_bonus_program_id=None,
        moysklad_bonus_transaction_id=None,
        bonus_points_credited=None,
        bonus_rubles_credited=None,
        wallet_synced_at=None,
        wallet_sync_error=None,
        wallet_reversal_transaction_id=None,
        wallet_reversed_at=None,
    )


def _client() -> SimpleNamespace:
    return SimpleNamespace(
        is_configured=lambda: True,
        get_counterparty=AsyncMock(
            return_value={
                "id": str(COUNTERPARTY_ID),
                "bonusPoints": 500,
                "bonusProgram": {
                    "id": str(PROGRAM_ID),
                    "name": "Постоянный клиент",
                    "active": True,
                    "spendRatePointsToRouble": 2,
                    "maxPaidRatePercents": 30,
                },
            }
        ),
        get_bonus_program=AsyncMock(),
        resolve_or_create_bonus_transaction=AsyncMock(
            return_value={
                "id": str(EARNING_ID),
                "transactionType": "EARNING",
                "applicable": True,
            }
        ),
    )


def test_bonus_points_for_rubles_uses_moysklad_program_rate() -> None:
    assert bonus_points_for_rubles(Decimal("123.45"), 2) == 247


def test_approved_partner_accrual_is_credited_to_moysklad_once() -> None:
    accrual = _approved_accrual()
    user = SimpleNamespace(
        id=19,
        email="buyer@example.com",
        moysklad_counterparty_id=COUNTERPARTY_ID,
    )
    db = SimpleNamespace(get=AsyncMock(return_value=user))
    client = _client()

    first_outcome = asyncio.run(
        sync_referral_accrual_to_bonus_wallet(
            db,
            accrual=accrual,
            moysklad_client=client,
        )
    )
    second_outcome = asyncio.run(
        sync_referral_accrual_to_bonus_wallet(
            db,
            accrual=accrual,
            moysklad_client=client,
        )
    )

    assert first_outcome == "credited"
    assert second_outcome == "credited"
    assert accrual.wallet_sync_status == "credited"
    assert accrual.moysklad_counterparty_id == COUNTERPARTY_ID
    assert accrual.moysklad_bonus_program_id == PROGRAM_ID
    assert accrual.moysklad_bonus_transaction_id == EARNING_ID
    assert accrual.bonus_points_credited == 247
    assert accrual.bonus_rubles_credited == Decimal("123.50")
    assert accrual.wallet_synced_at is not None
    client.resolve_or_create_bonus_transaction.assert_awaited_once_with(
        counterparty_id=COUNTERPARTY_ID,
        bonus_program_id=PROGRAM_ID,
        bonus_points=247,
        transaction_type="EARNING",
        external_code="elixir-partner-accrual-81",
        name="Партнёрское начисление EP-WALLET1",
        description=(
            "Подтверждённое партнёрское начисление уровня 1 "
            "по заказу приложения EP-WALLET1"
        ),
    )


def test_rejected_credited_accrual_is_reversed_idempotently() -> None:
    accrual = _approved_accrual()
    accrual.status = "rejected"
    accrual.wallet_sync_status = "credited"
    accrual.moysklad_counterparty_id = COUNTERPARTY_ID
    accrual.moysklad_bonus_program_id = PROGRAM_ID
    accrual.moysklad_bonus_transaction_id = EARNING_ID
    accrual.bonus_points_credited = 247
    accrual.bonus_rubles_credited = Decimal("123.50")
    db = SimpleNamespace()
    client = _client()
    client.resolve_or_create_bonus_transaction.return_value = {
        "id": str(REVERSAL_ID),
        "transactionType": "SPENDING",
        "applicable": True,
    }

    first_outcome = asyncio.run(
        sync_referral_accrual_to_bonus_wallet(
            db,
            accrual=accrual,
            moysklad_client=client,
        )
    )
    second_outcome = asyncio.run(
        sync_referral_accrual_to_bonus_wallet(
            db,
            accrual=accrual,
            moysklad_client=client,
        )
    )

    assert first_outcome == "reversed"
    assert second_outcome == "reversed"
    assert accrual.wallet_sync_status == "reversed"
    assert accrual.wallet_reversal_transaction_id == REVERSAL_ID
    assert accrual.wallet_reversed_at is not None
    client.resolve_or_create_bonus_transaction.assert_awaited_once()
