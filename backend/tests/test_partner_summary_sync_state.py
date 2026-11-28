from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.app.services.referrals import bitrix_sync, summary
from src.database.models import ReferralProfile
from src.integrations.bitrix_promo import BitrixPromoError


@pytest.mark.anyio
@pytest.mark.parametrize("profile_ok", [False, True], ids=["profile-outage", "summary-outage"])
async def test_partner_summary_partial_sync(monkeypatch, profile_ok):
    profile = ReferralProfile(
        reward_program="partner", reward_program_selection_source="promo_attached",
        reward_program_snapshot={}, referral_discount_base_total=Decimal("42"), bitrix_sync_status="pending",
    )
    user = SimpleNamespace(id=1, email="test@example.invalid", promo_code="REF")
    wallet = SimpleNamespace(balance_points=0, balance_rubles=0, spend_rate_points_to_ruble=1, is_loaded=True)
    for module in (summary, bitrix_sync):
        monkeypatch.setattr(module, "ensure_default_reward_program", AsyncMock(return_value=profile))
        monkeypatch.setattr(module, "bitrix_promo_configured", lambda: True)
    monkeypatch.setattr(summary, "get_user_moysklad_bonus_wallet", AsyncMock(return_value=wallet))
    monkeypatch.setattr(summary, "pending_loyalty_bonus_points", AsyncMock(return_value=0))
    monkeypatch.setattr(summary, "loyalty_bonus_expiration_summary", AsyncMock(return_value={
        "expiring_points": 0, "next_expires_at": None, "warning_days": 0,
    }))
    monkeypatch.setattr(summary, "_local_month_purchase_total", AsyncMock(return_value=Decimal("42")))
    monkeypatch.setattr(summary, "_local_partner_totals", AsyncMock(return_value=(Decimal("1"), 0, 0)))
    outage = BitrixPromoError(status_code=503, code="temporarily_unavailable", message="unavailable")
    client = SimpleNamespace(
        profile=AsyncMock(return_value={"user_id": 8, "program_profile": {"referrer_promo": "REF"}},
                          side_effect=None if profile_ok else outage),
        partner_summary=AsyncMock(return_value={"user_id": 8}, side_effect=outage if profile_ok else None),
    )
    for module in (summary, bitrix_sync):
        monkeypatch.setattr(module, "BitrixPromoClient", lambda: client)

    result = await summary.get_referral_profile_summary(AsyncMock(), user=user)

    assert result["bitrix_sync_status"] == "failed"
    assert result["bitrix_profile_found"] is profile_ok
    assert "temporarily_unavailable" in profile.bitrix_sync_error
    assert result["current_month_purchases"] == 42
    assert result["partner_pending_rubles"] == 1
    client.profile.assert_awaited_once()
    assert client.partner_summary.await_count == int(profile_ok)
