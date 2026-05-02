import json
import random

from typing import Any, Mapping

from .constants import CACHE_TTL_JITTER_RATIO


def _normalize_query_text(value: str | None, *, lower: bool = False) -> str | None:
    if value is None: return None
    normalized = " ".join(value.strip().split())
    if not normalized: return None
    if lower: normalized = normalized.lower()
    return normalized


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, str): return _normalize_query_text(value) or ""
    if isinstance(value, float): return round(value, 6)
    return value


def build_cache_key(*, route: str, params: Mapping[str, Any]) -> str:
    normalized_params = {key: _normalize_scalar(value) for key, value in sorted(params.items(), key=lambda item: item[0])}
    return f"{route}:{json.dumps(normalized_params, sort_keys=True, separators=(',', ':'), ensure_ascii=False)}"


def jitter_ttl_seconds(ttl_seconds: int, *, ratio: float = CACHE_TTL_JITTER_RATIO) -> int:
    ttl = max(1, int(ttl_seconds))
    spread = max(1, int(ttl * ratio))
    return max(1, ttl + random.randint(-spread, spread))