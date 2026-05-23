import base64
import hashlib

from typing import Any
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .constants import (
    APP_INTEGRITY_IOS_ALLOWED_ENVIRONMENTS,
    APP_INTEGRITY_IOS_BUNDLE_ID,
    APP_INTEGRITY_IOS_TEAM_ID,
    APP_INTEGRITY_MODE,
    APP_INTEGRITY_MODES,
    APPLE_APP_ATTEST_AAGUIDS,
)


def mode() -> str: return APP_INTEGRITY_MODE if APP_INTEGRITY_MODE in APP_INTEGRITY_MODES else "enforce"
def csv_values(value: str | None) -> set[str]:
    if not value: return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def sha256(data: bytes) -> bytes: return hashlib.sha256(data).digest()
def decode_base64(value: str) -> bytes:
    normalized = value.strip()
    padding = "=" * (-len(normalized) % 4)
    return base64.urlsafe_b64decode(f"{normalized}{padding}")


def encode_base64(value: bytes) -> str: return base64.b64encode(value).decode("ascii")
def public_key_x962_hash(public_key: ec.EllipticCurvePublicKey) -> str:
    public_key_bytes = public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return encode_base64(sha256(public_key_bytes))


def is_truthy_verdict(payload: Any) -> bool:
    if not isinstance(payload, dict): return False
    return bool(payload.get("ok") or payload.get("valid") or payload.get("allow"))


def ios_app_id() -> str | None:
    if not APP_INTEGRITY_IOS_TEAM_ID or not APP_INTEGRITY_IOS_BUNDLE_ID: return None
    return f"{APP_INTEGRITY_IOS_TEAM_ID}.{APP_INTEGRITY_IOS_BUNDLE_ID}"


def ios_allowed_environments() -> set[str]: return csv_values(APP_INTEGRITY_IOS_ALLOWED_ENVIRONMENTS) or {"production"}
def ios_environment_from_aaguid(aaguid: bytes) -> str | None:
    for environment, expected_aaguid in APPLE_APP_ATTEST_AAGUIDS.items():
        if hmac_compare_digest(aaguid, expected_aaguid): return environment
    return None


def hmac_compare_digest(a: bytes | str, b: bytes | str) -> bool:
    import hmac
    return hmac.compare_digest(a, b)
