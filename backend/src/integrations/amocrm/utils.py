import re

from typing import Any


def normalize_phone(value: str | None) -> str | None:
    if value is None: return None
    normalized = re.sub(r"[\s()-]", "", value.strip())
    return normalized or None


def extract_email_from_contact_obj(contact: dict[str, Any]) -> str | None:
    cfs = contact.get("custom_fields_values") or []
    if not isinstance(cfs, list): return None

    for cf in cfs:
        if not isinstance(cf, dict): continue

        code = str(cf.get("field_code") or "").upper()
        name = str(cf.get("field_name") or "").lower()

        if code == "EMAIL" or "email" in name or "почта" in name:
            for value in cf.get("values") or []:
                candidate = (value or {}).get("value")
                if isinstance(candidate, str) and "@" in candidate: return candidate.strip().lower()

    return None


def extract_phone_from_contact_obj(contact: dict[str, Any]) -> str | None:
    cfs = contact.get("custom_fields_values") or []
    if not isinstance(cfs, list): return None
    for cf in cfs:
        if not isinstance(cf, dict): continue
        code = str(cf.get("field_code") or "").upper()
        name = str(cf.get("field_name") or "").lower()
        if code == "PHONE" or "тел" in name or "phone" in name:
            for value in cf.get("values") or []:
                candidate = (value or {}).get("value")
                if isinstance(candidate, str):
                    normalized = normalize_phone(candidate)
                    if normalized: return normalized

    return None