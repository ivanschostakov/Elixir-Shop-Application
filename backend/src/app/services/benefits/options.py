from dataclasses import asdict
from decimal import Decimal

from .types import ResolvedDiscountOption


def best_option_key(option: ResolvedDiscountOption) -> tuple[int, Decimal, Decimal, Decimal]:
    estimated = option.estimated_discount_amount or Decimal("-0.01")
    percent = option.discount_percent or Decimal("-0.01")
    fixed = option.discount_amount or Decimal("-0.01")
    return 1 if option.is_applicable else 0, estimated, percent, fixed


def serialize_options(options: list[ResolvedDiscountOption]) -> list[dict]:
    return [asdict(option) for option in options]
