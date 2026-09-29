from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class SettlementRead(BaseModel):
    source: Literal["moysklad"] = "moysklad"
    status: Literal["fresh", "stale", "unavailable", "unlinked"]
    balance_rubles: Decimal | None = None
    total_purchases_rubles: Decimal | None = None
    loyalty_program: Literal[0, 1, 2] | None = None
    own_promo_code: str | None = None
    referrer_promo_code: str | None = None
    fetched_at: datetime | None = None
    issue: str | None = None
