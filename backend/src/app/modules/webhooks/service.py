import codecs
import re
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address, ip_network
from typing import Any
from urllib.parse import parse_qsl

from fastapi import Request
from src.integrations.amocrm.constants import PAID_STATUS_IDS, STATUS_IDS, STATUS_WORDS

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


# A checkout can emit its callback before the local transaction commits. This is
# a short reconciliation window, not a policy for importing historical CRM state.
AMO_LINK_WINDOW = timedelta(hours=1)
_APP_ORDER_TITLE = re.compile(r"Заказ №(EP-[A-Z0-9]{8}|[0-9]{1,19}) с Приложения", re.I | re.ASCII)


def amocrm_title_code(name):
    match = _APP_ORDER_TITLE.fullmatch((name or "").strip())
    return match[1].upper() if match else None


def amocrm_event_time(payload, received_at):
    timestamps = []
    for key in ("updated_at", "last_modified"):
        raw = _first_payload_value(payload, f"leads[status][0][{key}]")
        if raw:
            if not re.fullmatch("[0-9]{1,10}", raw):
                return None
            timestamps.append(datetime.fromtimestamp(int(raw), timezone.utc))
    return min(timestamps, default=received_at)


def amocrm_transition_concern(order, *, previous, target, received_at, event_at):
    if order.created_at > received_at or order.created_at.replace(microsecond=0) > event_at:
        return "event_predates_order"
    label = STATUS_WORDS.get(target)
    if label is None:
        return "unknown_status"
    canceled = {STATUS_IDS["canceled"], STATUS_IDS["refund_declined"]}
    if ((order.is_canceled or order.payment_status == "refunded") and target not in canceled
            or not order.is_active and order.status != label):
        return "terminal_order"
    if previous and order.status not in {STATUS_WORDS.get(previous), label}:
        return "previous_status_mismatch"
    if not previous and order.updated_at > received_at and order.status != label:
        return "order_changed_since_receipt"
    ranks = [STATUS_IDS[k] for k in ("check_paid", "packaged", "package_sent", "package_delivered", "won")]
    if order.status == STATUS_WORDS[STATUS_IDS["pending_payment"]] and target == STATUS_IDS["main"]:
        return "backward_transition"
    if target not in canceled:
        rank = ranks.index(target) if target in ranks else -1
        if (order.is_shipped and rank < ranks.index(STATUS_IDS["package_sent"])) or (order.is_paid and target not in PAID_STATUS_IDS):
            return "backward_transition"
        if any(order.status == STATUS_WORDS[stage] and rank < i for i, stage in enumerate(ranks)):
            return "backward_transition"
    elif (order.is_paid or order.is_shipped) and not previous and order.status != label:
        return "unconfirmed_cancellation"
    return None


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
