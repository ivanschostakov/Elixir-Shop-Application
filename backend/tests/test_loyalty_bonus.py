from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import src.app.services.referrals.program as reward_program_service
import src.app.services.referrals.promo as referral_promo_service
import src.app.modules.products.helpers as product_helpers
import src.app.services.benefits.loyalty as loyalty_service
from src.app.services.benefits.loyalty import (
    REWARD_MODE_CASHBACK,
    REWARD_MODE_PROMO,
    cashback_points_for_amount,
    grant_order_cashback_safe,
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


@pytest.mark.anyio
async def test_promo_order_does_not_grant_cashback(monkeypatch):
    create_credit = AsyncMock()
    monkeypatch.setattr(
        loyalty_service,
        "create_loyalty_bonus_credit",
        create_credit,
    )
    order = SimpleNamespace(
        id=84,
        is_paid=True,
        is_canceled=False,
        grand_total=Decimal("194.00"),
        delivery_total=Decimal("0.00"),
        payment_paid_at=None,
        checkout_snapshot={
            "benefits": {
                "reward_program": "bonus",
                "reward_mode": "promo",
                "entered_code": "REFERRER",
                "total_after_discounts": 194,
                "cashback_earned_points": 9,
            }
        },
    )
    user = SimpleNamespace(id=18)

    credit = await grant_order_cashback_safe(
        SimpleNamespace(),
        order=order,
        user=user,
    )

    assert credit is None
    create_credit.assert_not_awaited()


@pytest.mark.anyio
async def test_order_without_promo_still_grants_five_percent_cashback(monkeypatch):
    expected_credit = object()
    create_credit = AsyncMock(return_value=expected_credit)
    monkeypatch.setattr(
        loyalty_service,
        "create_loyalty_bonus_credit",
        create_credit,
    )
    order = SimpleNamespace(
        id=85,
        is_paid=True,
        is_canceled=False,
        grand_total=Decimal("200.00"),
        delivery_total=Decimal("0.00"),
        payment_paid_at=None,
        checkout_snapshot={
            "benefits": {
                "reward_program": "bonus",
                "reward_mode": "cashback",
                "entered_code": None,
                "total_after_discounts": 200,
                "cashback_earned_points": 10,
            }
        },
    )

    credit = await grant_order_cashback_safe(
        SimpleNamespace(),
        order=order,
        user=SimpleNamespace(id=19),
    )

    assert credit is expected_credit
    assert create_credit.await_args.kwargs["points"] == 10


@pytest.mark.anyio
async def test_attached_promo_must_be_unlinked_before_another_can_be_used(monkeypatch):
    profile = SimpleNamespace()
    monkeypatch.setattr(
        referral_promo_service,
        "_get_program_profile",
        AsyncMock(return_value=profile),
    )
    user = SimpleNamespace(promo_code="CURRENT")

    with pytest.raises(HTTPException) as error:
        await referral_promo_service.attach_referrer_code(
            SimpleNamespace(),
            user=user,
            code="NEW-CODE",
        )

    assert error.value.status_code == 409
    assert "Сначала отвяжите текущий промокод" in error.value.detail


def test_program_choice_is_not_required_at_30000():
    profile = SimpleNamespace(
        referral_discount_base_total=Decimal("29999.99"),
        reward_program_selection_source="system_default",
    )
    assert reward_program_selection_available(profile) is False
    assert reward_program_selection_required(profile) is False
    profile.referral_discount_base_total = Decimal("30000.00")
    assert reward_program_selection_available(profile) is True
    assert reward_program_selection_required(profile) is False
    profile.reward_program_selection_source = "user"
    assert reward_program_selection_required(profile) is False
    profile.reward_program_selection_source = "system_existing_promo"
    assert reward_program_selection_required(profile) is False


@pytest.mark.anyio
async def test_system_default_profile_with_existing_promo_gets_base_discount(monkeypatch):
    profile = SimpleNamespace(
        reward_program="bonus",
        reward_program_selected_at=None,
        reward_program_selection_source="system_default",
        reward_program_snapshot={"migrated_from": "combined"},
        referral_discount_base_total=Decimal("6840.18"),
        current_discount_percent=Decimal("3.00"),
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
    assert restored.reward_program_selection_source == "promo_attached"
    assert restored.reward_program_selected_at is not None
    assert restored.reward_program_snapshot["active_promo"] == "EXISTING-PROMO"
    assert restored.current_discount_percent == Decimal("3.00")
    db.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_inferred_existing_promo_partner_is_normalized_to_promo_activation(monkeypatch):
    profile = SimpleNamespace(
        reward_program="partner",
        reward_program_selected_at=object(),
        reward_program_selection_source="system_existing_promo",
        reward_program_snapshot={"recovered_existing_promo": "slim101"},
        referral_discount_base_total=Decimal("30000.00"),
        current_discount_percent=Decimal("3.00"),
    )
    user = SimpleNamespace(promo_code="slim101")
    db = SimpleNamespace(flush=AsyncMock())
    monkeypatch.setattr(
        reward_program_service,
        "get_or_create_referral_profile",
        AsyncMock(return_value=profile),
    )

    repaired = await ensure_default_reward_program(db, user=user)

    assert repaired.reward_program == "partner"
    assert repaired.reward_program_selected_at is not None
    assert repaired.reward_program_selection_source == "promo_attached"
    assert repaired.reward_program_snapshot["active_promo"] == "slim101"
    assert repaired.current_discount_percent == Decimal("3.00")


@pytest.mark.anyio
async def test_base_promo_discounts_products_in_bonus_program(monkeypatch):
    user = SimpleNamespace(id=18, promo_code="slim101")
    profile = SimpleNamespace(
        reward_program="bonus",
        current_discount_percent=Decimal("3.00"),
    )
    monkeypatch.setattr(
        product_helpers,
        "get_referral_profile_by_user_id",
        AsyncMock(return_value=profile),
    )

    discount = await product_helpers.get_user_product_discount_percent(
        SimpleNamespace(),
        user,
    )

    assert discount == Decimal("3.00")
