import logging

from typing import Any
from fastapi import HTTPException

secure_log = logging.getLogger("secure.external")


def _compact(value: Any, *, max_length: int = 4000) -> str:
    if value is None: return ""
    raw = str(value).strip()
    if len(raw) <= max_length: return raw
    return f"{raw[:max_length]}...[truncated]"


def external_service_http_exception(*, service: str, operation: str, public_detail: str, status_code: int = 502, raw_detail: Any | None = None, extra: dict[str, Any] | None = None, exc: Exception | None = None) -> HTTPException:
    secure_log.error("external_service_failure service=%s operation=%s raw_detail=%s extra=%s", service, operation, _compact(raw_detail), _compact(extra), exc_info=exc)
    return HTTPException(status_code=status_code, detail=public_detail)
