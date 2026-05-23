import codecs
import re
from ipaddress import ip_address, ip_network
from typing import Any
from urllib.parse import parse_qsl

from fastapi import Request

from config import AMOCRM_ACCOUNT_ID, AMOCRM_WEBHOOK_ALLOWED_ACCOUNT_IDS, AMOCRM_WEBHOOK_ALLOWED_IPS, AMOCRM_WEBHOOK_ALLOWED_SUBDOMAINS

_INTELLECTMONEY_PAYLOAD_KEYS = {
    "eshopaccount": "EshopAccount",
    "eshopid": "EshopId",
    "hash": "Hash",
    "orderid": "OrderId",
    "paymentdata": "PaymentData",
    "paymentid": "PaymentId",
    "paymentstatus": "PaymentStatus",
    "recipientamount": "RecipientAmount",
    "recipientcurrency": "RecipientCurrency",
    "recipientoriginalamount": "RecipientOriginalAmount",
    "secretkey": "SecretKey",
    "servicename": "ServiceName",
    "useremail": "UserEmail",
    "username": "UserName",
}

def _coerce_amocrm_int(value: Any, field: str) -> int:
    raw = value or "0"
    try: return int(raw)
    except (TypeError, ValueError): return 0


def _amocrm_payload_int(payload: dict[str, list[str]], key: str) -> int:
    raw = (payload.get(key) or ["0"])[0] or "0"
    return _coerce_amocrm_int(raw, key)


def _intellectmoney_form_charset(content_type: str | None) -> str:
    match = re.search(r"(?i)(?:^|;)\s*charset\s*=\s*([^;]+)", content_type or "")
    charset = (match.group(1).strip().strip("\"'") if match else "") or "utf-8"
    if charset.lower() in {"windows-1251", "win-1251"}: charset = "cp1251"
    try: codecs.lookup(charset)
    except LookupError: return "utf-8"
    return charset


def _parse_intellectmoney_payload(body: bytes, content_type: str | None) -> tuple[dict[str, str], str]:
    charset = _intellectmoney_form_charset(content_type)
    text = body.decode(charset, "replace")
    payload: dict[str, str] = {}
    for key, value in parse_qsl(text, keep_blank_values=True, encoding=charset, errors="replace"):
        canonical_key = _INTELLECTMONEY_PAYLOAD_KEYS.get(str(key).lower(), str(key))
        payload[canonical_key] = str(value)

    return payload, charset


def _header_value(request: Request, *names: str) -> str | None:
    for name in names:
        value = (request.headers.get(name) or "").strip()
        if value: return value
    return None


def _first_payload_value(payload: dict[str, list[str]], key: str) -> str:
    return str((payload.get(key) or [""])[0] or "").strip()


def _request_client_ip(request: Request) -> str:
    forwarded_for = _header_value(request, "x-forwarded-for")
    if forwarded_for: return forwarded_for.split(",", 1)[0].strip()
    real_ip = _header_value(request, "x-real-ip")
    if real_ip: return real_ip
    return (request.client.host if request.client else "").strip()


def _ip_allowed(ip_raw: str, allowed_networks: list[str]) -> bool:
    if not allowed_networks: return True
    try: client_ip = ip_address(ip_raw)
    except ValueError: return False
    for network_raw in allowed_networks:
        candidate = network_raw.strip()
        if not candidate: continue
        try:
            if "/" in candidate and client_ip in ip_network(candidate, strict=False): return True
            elif client_ip == ip_address(candidate): return True
        except ValueError: continue
    return False


def _amocrm_webhook_verified(request: Request, payload: dict[str, list[str]]) -> bool:
    account_id = _first_payload_value(payload, "account[id]")
    account_subdomain = _first_payload_value(payload, "account[subdomain]").lower()
    allowed_account_ids = [value.strip() for value in AMOCRM_WEBHOOK_ALLOWED_ACCOUNT_IDS if value.strip()]
    if not allowed_account_ids and AMOCRM_ACCOUNT_ID: allowed_account_ids = [str(AMOCRM_ACCOUNT_ID).strip()]
    allowed_subdomains = [value.strip().lower() for value in AMOCRM_WEBHOOK_ALLOWED_SUBDOMAINS if value.strip()]
    if allowed_account_ids and account_id not in allowed_account_ids: return False
    if allowed_subdomains and account_subdomain not in allowed_subdomains: return False
    return _ip_allowed(_request_client_ip(request), AMOCRM_WEBHOOK_ALLOWED_IPS)
