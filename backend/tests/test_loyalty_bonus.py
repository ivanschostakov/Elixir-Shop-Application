from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

import src.app.services.referrals.program as reward_program_service
from src.app.services.benefits.loyalty import (
    REWARD_MODE_CASHBACK,
    REWARD_MODE_PROMO,
    cashback_points_for_amount,
    normalize_reward_mode,
)
from config import LOYALTY_BONUS_LIFETIME_DAYS, LOYALTY_EXPIRY_WARNING_DAYS
from src.app.services.referrals.program import (
    ensure_default_reward_program,
    reward_program_selection_available,
    reward_program_selection_required,
)
from types import SimpleNamespace


def test_cashback_uses_five_percent_and_whole_points():
    assert cashback_points_for_amount(Decimal("1000.00")) == 50
    assert cashback_points_for_amount(Decimal("199.99")) == 9


def test_reward_mode_defaults_to_cashback_without_entered_code():
    assert normalize_reward_mode(None) == REWARD_MODE_CASHBACK


def test_legacy_request_with_entered_code_defaults_to_promo():
    assert normalize_reward_mode(None, has_entered_code=True) == REWARD_MODE_PROMO


def test_explicit_cashback_wins_even_when_user_has_a_promo():
    assert normalize_reward_mode("cashback", has_entered_code=True) == REWARD_MODE_CASHBACK


def test_bonus_expiry_terms_match_approved_rules():
    assert LOYALTY_BONUS_LIFETIME_DAYS == 60
    assert LOYALTY_EXPIRY_WARNING_DAYS == 14


def test_program_choice_is_offered_at_30000_until_explicitly_selected():
    profile = SimpleNamespace(
        referral_discount_base_total=Decimal("29999.99"),
        reward_program_selection_source="system_default",
    )
    assert reward_program_selection_available(profile) is False
    assert reward_program_selection_required(profile) is False
    profile.referral_discount_base_total = Decimal("30000.00")
    assert reward_program_selection_available(profile) is True
    assert reward_program_selection_required(profile) is True
    profile.reward_program_selection_source = "user"
    assert reward_program_selection_required(profile) is False
    profile.reward_program_selection_source = "system_existing_promo"
    assert reward_program_selection_required(profile) is False


@pytest.mark.anyio
async def test_system_default_profile_with_existing_promo_is_restored_to_partner(monkeypatch):
    profile = SimpleNamespace(
        reward_program="bonus",
        reward_program_selected_at=None,
        reward_program_selection_source="system_default",
        reward_program_snapshot={"migrated_from": "combined"},
    )
    user = SimpleNamespace(promo_code="EXISTING-PROMO")
    db = SimpleNamespace(flush=AsyncMock())
    monkeypatch.setattr(
        reward_program_service,
        "get_or_create_referral_profile",
        AsyncMock(return_value=profile),
    )

    restored = await ensure_default_reward_program(db, user=user)

    assert restored.reward_program == "partner"
    assert restored.reward_program_selection_source == "system_existing_promo"
    assert restored.reward_program_selected_at is not None
    assert restored.reward_program_snapshot["recovered_existing_promo"] == "EXISTING-PROMO"
    db.flush.assert_awaited_once()
