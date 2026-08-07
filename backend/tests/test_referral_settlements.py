import asyncio
from decimal import Decimal
from types import SimpleNamespace

from src.app.services.admin.referrals import mark_settlement_transferred


class _ScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _FakeSession:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _statement):
        return _ScalarRows(self.rows)


def test_mark_settlement_transferred_moves_approved_rows_out_of_deposit_queue():
    rows = [
        SimpleNamespace(
            commission_amount=Decimal("125.50"),
            settlement_method="deposit",
            settlement_reference=None,
            settled_at=None,
            settled_by_admin_user_id=None,
            wallet_sync_status="pending",
            wallet_sync_error="retry",
        ),
        SimpleNamespace(
            commission_amount=Decimal("74.50"),
            settlement_method="deposit",
            settlement_reference=None,
            settled_at=None,
            settled_by_admin_user_id=None,
            wallet_sync_status="waiting_for_wallet",
            wallet_sync_error=None,
        ),
    ]

    result = asyncio.run(
        mark_settlement_transferred(
            _FakeSession(rows),
            beneficiary_bitrix_user_id=42,
            period="2026-07",
            currency="rub",
            reference="BANK-1001",
            admin_user_id=7,
        )
    )

    assert result is not None
    assert result["currency"] == "RUB"
    assert result["accruals_count"] == 2
    assert result["transferred_amount"] == Decimal("200.00")
    assert all(row.settlement_method == "transfer" for row in rows)
    assert all(row.wallet_sync_status == "transferred" for row in rows)
    assert all(row.settlement_reference == "BANK-1001" for row in rows)
    assert all(row.settled_by_admin_user_id == 7 for row in rows)
    assert all(row.settled_at is not None for row in rows)
