from dataclasses import dataclass
from datetime import datetime
from typing import Literal

RecommendationSurface = Literal["home", "product", "cart", "draft"]


@dataclass(slots=True)
class CategoryAffinity:
    score: int = 0
    last_signal_at: datetime | None = None

