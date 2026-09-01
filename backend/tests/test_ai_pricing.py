from datetime import datetime, timezone
from decimal import Decimal

from src.app.services.ai.pricing import calculate_openai_text_cost


def _cost(model: str, when: datetime, *, input_tokens: int, cached_tokens: int, output_tokens: int) -> Decimal:
    result = calculate_openai_text_cost(
        model=model,
        occurred_at=when,
        input_tokens=input_tokens,
        cached_input_tokens=cached_tokens,
        output_tokens=output_tokens,
    )
    assert result is not None
    return result.cost_usd


def test_sol_uses_historical_rate_at_request_date():
    before_promotion = _cost(
        "gpt-5.6-sol",
        datetime(2026, 8, 20, tzinfo=timezone.utc),
        input_tokens=200_000,
        cached_tokens=0,
        output_tokens=100_000,
    )
    after_promotion = _cost(
        "gpt-5.6-sol",
        datetime(2026, 8, 21, tzinfo=timezone.utc),
        input_tokens=200_000,
        cached_tokens=0,
        output_tokens=100_000,
    )

    assert before_promotion == Decimal("4.00000000")
    assert after_promotion == Decimal("2.80000000")


def test_cached_input_is_not_charged_twice():
    result = _cost(
        "gpt-5.6-terra",
        datetime(2026, 9, 1, tzinfo=timezone.utc),
        input_tokens=200_000,
        cached_tokens=150_000,
        output_tokens=20_000,
    )

    assert result == Decimal("0.37000000")


def test_long_context_multiplier_uses_full_request_input_size():
    result = _cost(
        "gpt-5.6-terra",
        datetime(2026, 9, 1, tzinfo=timezone.utc),
        input_tokens=300_000,
        cached_tokens=100_000,
        output_tokens=10_000,
    )

    assert result == Decimal("1.02000000")


def test_snapshot_model_and_unknown_model_handling():
    known = calculate_openai_text_cost(
        model="gpt-4.1-mini-2025-04-14",
        occurred_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        input_tokens=1_000,
        cached_input_tokens=0,
        output_tokens=100,
    )
    unknown = calculate_openai_text_cost(
        model="unknown-model",
        occurred_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        input_tokens=1_000,
        cached_input_tokens=0,
        output_tokens=100,
    )

    assert known is not None
    assert known.cost_usd == Decimal("0.00056000")
    assert unknown is None


def test_file_search_tool_calls_are_included():
    result = calculate_openai_text_cost(
        model="gpt-5.6-terra",
        occurred_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        input_tokens=0,
        cached_input_tokens=0,
        output_tokens=0,
        file_search_calls=3,
    )

    assert result is not None
    assert result.cost_usd == Decimal("0.00750000")
