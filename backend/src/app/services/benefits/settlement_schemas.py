from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel
from src.normalize import ms_referrer_code


class SettlementRead(BaseModel):
    source: Literal["moysklad"] = "moysklad"
    status: Literal["fresh", "stale", "unavailable", "unlinked"]
    balance_rubles: Decimal | None = None
    total_purchases_rubles: Decimal | None = None
    loyalty_program: Literal[0, 1, 2] | None = None
    personal_discount_percent: Decimal | None = None
    own_promo_code: str | None = None
    referrer_promo_code: Annotated[str | None, AfterValidator(ms_referrer_code)] = None
    fetched_at: datetime | None = None
    issue: str | None = None
