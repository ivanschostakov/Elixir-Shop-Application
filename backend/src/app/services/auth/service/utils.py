from fastapi import HTTPException, Request
from starlette import status
from src.app.services.rate_limit import client_ip_from_request
from src.database.limits import PERSON_NAME_MAX_LENGTH, PHONE_NUMBER_MAX_LENGTH, TELEGRAM_USERNAME_MAX_LENGTH
from src.normalize import normalize_email, normalize_phone, optional_str


def _auth_limit_key(request: Request, principal: str | None = None) -> str:
    ip = client_ip_from_request(request)
    normalized_principal = (principal or "").strip().lower()
    return f"{ip}:{normalized_principal}" if normalized_principal else ip


def _mask_email(email: str | None) -> str | None:
    normalized = normalize_email(email)
    if not normalized: return None
    local, _, domain = normalized.partition("@")
    if not local or not domain: return None
    masked_local = local[:2] + "*" * max(len(local) - 2, 1)
    return f"{masked_local}@{domain}"


def _counterparty_email(counterparty: dict[str, object] | None) -> str | None:
    if not isinstance(counterparty, dict): return None
    return normalize_email(counterparty.get("email"))


def _counterparty_name_parts(counterparty: dict[str, object] | None) -> tuple[str, str]:
    raw_name = optional_str(counterparty.get("name") if isinstance(counterparty, dict) else None) or "Customer"
    parts = raw_name.split()
    if len(parts) == 1: return raw_name[:PERSON_NAME_MAX_LENGTH], "Customer"
    return parts[0][:PERSON_NAME_MAX_LENGTH], " ".join(parts[1:])[:PERSON_NAME_MAX_LENGTH] or "Customer"


def _telegram_config_unavailable() -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telegram auth is not configured")


def _fit_person_name(value: object, fallback: str) -> str:
    normalized = optional_str(value) or fallback
    return normalized[:PERSON_NAME_MAX_LENGTH] or fallback


def _fit_telegram_username(value: object) -> str | None:
    normalized = optional_str(value)
    return normalized[:TELEGRAM_USERNAME_MAX_LENGTH] if normalized else None


def _normalize_telegram_phone(value: object) -> str | None:
    normalized = normalize_phone(value)
    if normalized is None: return None
    if not normalized.startswith("+"): normalized = f"+{normalized}"
    return normalized[:PHONE_NUMBER_MAX_LENGTH]
