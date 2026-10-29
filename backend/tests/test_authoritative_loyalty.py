import asyncio
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.app.services.referrals import program, bitrix_sync
from src.app.services.referrals.paid_orders import orders, reconciliation


def test_settlement_can_be_imported_without_initializing_api_routes():
    subprocess.run([sys.executable, "-c",
        "from src.app.services.benefits.settlement import get_account_settlement; "
        "from src.app.services.benefits.settlement_schemas import SettlementRead; "
        "assert SettlementRead(status='unlinked').status == 'unlinked'"], check=True)


def profile():
    return SimpleNamespace(id=1, reward_program="bonus", reward_program_selection_source="system_default",
        reward_program_selected_at=None, reward_program_snapshot={},
        referral_discount_base_total=Decimal("0"), current_discount_percent=Decimal("0"),
        bitrix_user_id=None, partner_unlocked_at=None)


@pytest.mark.parametrize("code,expected,promo", [(2, "partner", None), (1, "bonus", "OLD-PROMO"), (0, "bonus", None)])
def test_moysklad_program_is_not_inferred_from_promo(monkeypatch, code, expected, promo):
    row = profile()
    user = SimpleNamespace(id=1, moysklad_counterparty_id=uuid4(), promo_code="LOCAL")
    value = SimpleNamespace(status="fresh", loyalty_program=code,
        total_purchases_rubles=Decimal("43502.10"), referrer_promo_code=promo,
        own_promo_code="OWN", fetched_at=datetime.now(timezone.utc))
    monkeypatch.setattr(program, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    monkeypatch.setattr(program, "get_or_create_referral_profile", AsyncMock(return_value=row))
    monkeypatch.setattr("src.app.services.benefits.settlement.get_account_settlement", AsyncMock(return_value=value))
    db = SimpleNamespace(flush=AsyncMock())
    for _ in range(2):
        asyncio.run(program.ensure_default_reward_program(db, user=user))
        assert row.reward_program == expected
        assert row.reward_program_selection_source == "moysklad"
        assert row.referral_discount_base_total == Decimal("43502.10")
        assert user.promo_code == promo
        bitrix_sync.apply_bitrix_program_profile(row, user=user, program_profile={
            "referrer_promo": "STALE-BITRIX", "order_sum": {"amount": 90000},
            "stored_discount_percent": 20, "group_discount_percent": 20})
        assert row.reward_program == expected
        assert row.reward_program_selection_source == "moysklad"
        assert row.referral_discount_base_total == Decimal("43502.10")
        assert user.promo_code == promo
        assert row.current_discount_percent == (Decimal("4.00") if code == 2 else Decimal("0.00"))
    if code == 0:
        assert row.current_discount_percent == 0


def test_remote_outage_preserves_existing_account_program(monkeypatch):
    row = profile()
    cid = uuid4()
    row.reward_program = "partner"
    row.reward_program_selection_source = "moysklad"
    row.reward_program_snapshot = {"moysklad_program_code": 2, "moysklad_counterparty_id": str(cid)}
    user = SimpleNamespace(id=1, moysklad_counterparty_id=cid, promo_code=None)
    monkeypatch.setattr(program, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    monkeypatch.setattr(program, "get_or_create_referral_profile", AsyncMock(return_value=row))
    monkeypatch.setattr("src.app.services.benefits.settlement.get_account_settlement", AsyncMock(return_value=SimpleNamespace(status="unavailable", loyalty_program=None)))
    asyncio.run(program.ensure_default_reward_program(SimpleNamespace(flush=AsyncMock()), user=user))
    assert row.reward_program == "partner"
    assert row.reward_program_selection_source == "moysklad"


def test_accounting_partner_discount_does_not_require_a_referrer_promo():
    from src.app.services.benefits.service import _build_app_referral_option
    from src.app.services.referrals.profile import refresh_profile_discount
    row = profile()
    row.reward_program = "partner"
    row.reward_program_selection_source = "moysklad"
    row.referral_discount_base_total = Decimal("43502.10")
    refresh_profile_discount(row, has_promo_code=False)
    assert row.current_discount_percent == Decimal("4.00")
    option = _build_app_referral_option(row, user=SimpleNamespace(promo_code=None),
        subtotal=Decimal("1000"), discountable_subtotal=Decimal("1000"))
    assert option is not None and option.is_applicable
    assert option.discount_percent == Decimal("4.00")
    assert option.estimated_discount_amount == Decimal("40.00")


@pytest.mark.parametrize("name", ["sync_paid_order_referral_to_app", "reverse_paid_order_reward",
    "retry_unsynced_app_referral_purchases", "backfill_missing_paid_order_rewards", "finalize_closed_app_referral_accruals"])
def test_settlement_replays_never_post_or_reverse_referral_rewards(monkeypatch, name):
    module = orders if hasattr(orders, name) else reconciliation
    monkeypatch.setattr(module, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    db = SimpleNamespace(execute=AsyncMock(side_effect=AssertionError("No financial replay")),
                         commit=AsyncMock(side_effect=AssertionError("No financial replay")))
    for _ in range(3):
        kwargs = {"order": object()} if module is orders else {}
        result = asyncio.run(getattr(module, name)(db, **kwargs))
        assert result.get("outcome") == "managed_by_moysklad" or result.get("processed") == 0
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()
