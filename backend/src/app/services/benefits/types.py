from dataclasses import dataclass
from decimal import Decimal

IGNORED_USAGE_STATUSES = ("cancelled", "reversed", "failed")
PERCENT_BENEFIT_KINDS = {"percent", "percentage"}
FIXED_BENEFIT_KINDS = {"fixed", "fixed_amount", "amount"}


@dataclass(slots=True)
class ResolvedDiscountOption:
    source_kind: str
    source_record_id: int | None
    code: str | None
    title: str
    status: str
    is_applicable: bool
    is_personal: bool
    is_stackable: bool
    calculation_mode: str
    discount_percent: Decimal | None
    discount_amount: Decimal | None
    currency: str | None
    estimated_discount_amount: Decimal | None
    estimated_total_after: Decimal | None
    reason: str | None
