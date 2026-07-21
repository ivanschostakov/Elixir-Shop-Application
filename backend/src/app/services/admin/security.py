import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from config import (
    ADMIN_ACCESS_EXPIRE_MINUTES,
    ADMIN_CHALLENGE_EXPIRE_MINUTES,
    ADMIN_MFA_ISSUER,
    JWT_ACCESS_SECRET_KEY,
)

ALGORITHM = "HS256"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_admin_access_token(*, user_id: int, session_id: int) -> str:
    now = _now()
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "type": "admin_access",
        "aud": "admin",
        "iat": now,
        "exp": now + timedelta(minutes=ADMIN_ACCESS_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_ACCESS_SECRET_KEY, algorithm=ALGORITHM)


def create_admin_challenge_token(*, user_id: int, purpose: str) -> str:
    now = _now()
    payload = {
        "sub": str(user_id),
        "type": "admin_challenge",
        "purpose": purpose,
        "aud": "admin",
        "iat": now,
        "exp": now + timedelta(minutes=ADMIN_CHALLENGE_EXPIRE_MINUTES),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, JWT_ACCESS_SECRET_KEY, algorithm=ALGORITHM)


def decode_admin_token(token: str, *, expected_type: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            JWT_ACCESS_SECRET_KEY,
            algorithms=[ALGORITHM],
            audience="admin",
        )
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _normalized_secret(secret: str) -> bytes:
    normalized = "".join(secret.upper().split())
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    return base64.b32decode(normalized + padding, casefold=True)


def _totp_code(secret: str, counter: int) -> str:
    digest = hmac.new(_normalized_secret(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def verify_totp(secret: str, code: str, *, timestamp: float | None = None, window: int = 1) -> bool:
    normalized_code = "".join(str(code).split())
    if len(normalized_code) != 6 or not normalized_code.isdigit():
        return False
    counter = int((timestamp if timestamp is not None else time.time()) // 30)
    return any(hmac.compare_digest(_totp_code(secret, counter + delta), normalized_code) for delta in range(-window, window + 1))


def build_totp_uri(*, secret: str, email: str) -> str:
    issuer = ADMIN_MFA_ISSUER
    label = quote(f"{issuer}:{email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"


def _fernet() -> Fernet:
    key = hashlib.sha256(f"{JWT_ACCESS_SECRET_KEY}:admin-mfa".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_totp_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_totp_secret(encrypted_secret: str) -> str | None:
    try:
        return _fernet().decrypt(encrypted_secret.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        return None
