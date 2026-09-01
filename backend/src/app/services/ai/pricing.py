from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP


MILLION = Decimal("1000000")
LONG_CONTEXT_THRESHOLD = 272_000
COST_QUANTUM = Decimal("0.00000001")
FILE_SEARCH_CALL_USD = Decimal("0.0025")


@dataclass(frozen=True)
class OpenAITextRate:
    model_family: str
    effective_from: date
    input_usd_per_million: Decimal
    cached_input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    long_context_pricing: bool = False


@dataclass(frozen=True)
class OpenAIUsageCost:
    model: str
    rate: OpenAITextRate
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    file_search_calls: int
    long_context: bool
    cost_usd: Decimal

    def as_snapshot(self) -> dict[str, object]:
        return {
            "model": self.model,
            "currency": "USD",
            "cost_usd": float(self.cost_usd),
            "input_usd_per_million": float(self.rate.input_usd_per_million),
            "cached_input_usd_per_million": float(self.rate.cached_input_usd_per_million),
            "output_usd_per_million": float(self.rate.output_usd_per_million),
            "file_search_calls": self.file_search_calls,
            "file_search_usd_per_call": float(FILE_SEARCH_CALL_USD),
            "pricing_effective_from": self.rate.effective_from.isoformat(),
            "long_context": self.long_context,
            "basis": "actual_token_usage",
            "pricing_source": "openai_official",
        }


_RATES: dict[str, tuple[OpenAITextRate, ...]] = {
    "gpt-5.6-sol": (
        OpenAITextRate(
            model_family="gpt-5.6-sol",
            effective_from=date.min,
            input_usd_per_million=Decimal("5.00"),
            cached_input_usd_per_million=Decimal("0.50"),
            output_usd_per_million=Decimal("30.00"),
            long_context_pricing=True,
        ),
        OpenAITextRate(
            model_family="gpt-5.6-sol",
            effective_from=date(2026, 8, 21),
            input_usd_per_million=Decimal("4.00"),
            cached_input_usd_per_million=Decimal("0.40"),
            output_usd_per_million=Decimal("20.00"),
            long_context_pricing=True,
        ),
    ),
    "gpt-5.6-terra": (
        OpenAITextRate(
            model_family="gpt-5.6-terra",
            effective_from=date.min,
            input_usd_per_million=Decimal("2.50"),
            cached_input_usd_per_million=Decimal("0.25"),
            output_usd_per_million=Decimal("15.00"),
            long_context_pricing=True,
        ),
        OpenAITextRate(
            model_family="gpt-5.6-terra",
            effective_from=date(2026, 7, 30),
            input_usd_per_million=Decimal("2.00"),
            cached_input_usd_per_million=Decimal("0.20"),
            output_usd_per_million=Decimal("12.00"),
            long_context_pricing=True,
        ),
    ),
    "gpt-5.6-luna": (
        OpenAITextRate(
            model_family="gpt-5.6-luna",
            effective_from=date.min,
            input_usd_per_million=Decimal("1.00"),
            cached_input_usd_per_million=Decimal("0.10"),
            output_usd_per_million=Decimal("6.00"),
            long_context_pricing=True,
        ),
        OpenAITextRate(
            model_family="gpt-5.6-luna",
            effective_from=date(2026, 7, 30),
            input_usd_per_million=Decimal("0.20"),
            cached_input_usd_per_million=Decimal("0.02"),
            output_usd_per_million=Decimal("1.20"),
            long_context_pricing=True,
        ),
    ),
    "gpt-4.1-mini": (
        OpenAITextRate(
            model_family="gpt-4.1-mini",
            effective_from=date.min,
            input_usd_per_million=Decimal("0.40"),
            cached_input_usd_per_million=Decimal("0.10"),
            output_usd_per_million=Decimal("1.60"),
        ),
    ),
}


def _model_family(model: str) -> str | None:
    normalized = model.strip().lower()
    if normalized == "gpt-5.6" or normalized.startswith("gpt-5.6-sol"):
        return "gpt-5.6-sol"
    for family in ("gpt-5.6-terra", "gpt-5.6-luna", "gpt-4.1-mini"):
        if normalized.startswith(family):
            return family
    return None


def _usage_date(occurred_at: datetime | date) -> date:
    if isinstance(occurred_at, datetime):
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        return occurred_at.astimezone(timezone.utc).date()
    return occurred_at


def calculate_openai_text_cost(
    *,
    model: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    file_search_calls: int = 0,
    occurred_at: datetime | date,
) -> OpenAIUsageCost | None:
    family = _model_family(model)
    if family is None:
        return None

    usage_date = _usage_date(occurred_at)
    rate = max(
        (candidate for candidate in _RATES[family] if candidate.effective_from <= usage_date),
        key=lambda candidate: candidate.effective_from,
    )
    safe_input = max(int(input_tokens), 0)
    safe_cached = min(max(int(cached_input_tokens), 0), safe_input)
    safe_output = max(int(output_tokens), 0)
    safe_file_search_calls = max(int(file_search_calls), 0)
    uncached_input = safe_input - safe_cached
    long_context = rate.long_context_pricing and safe_input > LONG_CONTEXT_THRESHOLD
    input_multiplier = Decimal("2") if long_context else Decimal("1")
    output_multiplier = Decimal("1.5") if long_context else Decimal("1")
    cost = (
        Decimal(uncached_input) * rate.input_usd_per_million * input_multiplier
        + Decimal(safe_cached) * rate.cached_input_usd_per_million * input_multiplier
        + Decimal(safe_output) * rate.output_usd_per_million * output_multiplier
    ) / MILLION + Decimal(safe_file_search_calls) * FILE_SEARCH_CALL_USD
    return OpenAIUsageCost(
        model=model,
        rate=rate,
        input_tokens=safe_input,
        cached_input_tokens=safe_cached,
        output_tokens=safe_output,
        file_search_calls=safe_file_search_calls,
        long_context=long_context,
        cost_usd=cost.quantize(COST_QUANTUM, rounding=ROUND_HALF_UP),
    )


__all__ = ["OpenAIUsageCost", "calculate_openai_text_cost"]
