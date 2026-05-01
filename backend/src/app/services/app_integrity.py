import hmac
import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import timedelta, timezone
from typing import Any
from urllib.parse import quote

import cbor2
import google.auth
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleAuthRequest
import httpx
from anyio import to_thread
from fastapi import Depends, HTTPException, Request
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils as asymmetric_utils
from cryptography.x509.oid import ExtensionOID, ObjectIdentifier
from pyasn1.codec.der import decoder as der_decoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import (
    APP_INTEGRITY_ANDROID_ALLOWED_DEVICE_VERDICTS,
    APP_INTEGRITY_ANDROID_CERT_SHA256_DIGESTS,
    APP_INTEGRITY_ANDROID_PACKAGE_NAME,
    APP_INTEGRITY_CHALLENGE_TTL_SECONDS,
    APP_INTEGRITY_DEV_TOKEN,
    APP_INTEGRITY_IOS_ALLOWED_ENVIRONMENTS,
    APP_INTEGRITY_IOS_BUNDLE_ID,
    APP_INTEGRITY_IOS_TEAM_ID,
    APP_INTEGRITY_MODE,
    APP_INTEGRITY_TOKEN_MAX_AGE_SECONDS,
    APP_INTEGRITY_VERIFIER_TIMEOUT_SECONDS,
    APP_INTEGRITY_VERIFIER_URL,
    ufa_now,
)
from src.app.modules.auth.dependencies import get_current_user
from src.database import get_db
from src.database.models import AppAttestKey, AppIntegrityChallenge, User

log = logging.getLogger(__name__)

APP_INTEGRITY_TOKEN_HEADER = "x-app-integrity-token"
APP_INTEGRITY_PLATFORM_HEADER = "x-app-integrity-platform"
APP_INTEGRITY_ACTION_HEADER = "x-app-integrity-action"
APP_INTEGRITY_REQUEST_HASH_HEADER = "x-app-integrity-request-hash"
APP_INTEGRITY_KEY_ID_HEADER = "x-app-integrity-key-id"
APP_INTEGRITY_MODES = {"off", "monitor", "enforce"}
PLAY_INTEGRITY_SCOPE = "https://www.googleapis.com/auth/playintegrity"
APPLE_APP_ATTEST_NONCE_OID = ObjectIdentifier("1.2.840.113635.100.8.2")
APPLE_APP_ATTEST_AAGUIDS = {
    "production": b"appattest" + (b"\x00" * 7),
    "development": b"appattestdevelop",
    "sandbox": b"appattestsandbox",
}
APPLE_APP_ATTEST_ROOT_CA_PEM = b"""-----BEGIN CERTIFICATE-----
MIICITCCAaegAwIBAgIQC/O+DvHN0uD7jG5yH2IXmDAKBggqhkjOPQQDAzBSMSYw
JAYDVQQDDB1BcHBsZSBBcHAgQXR0ZXN0YXRpb24gUm9vdCBDQTETMBEGA1UECgwK
QXBwbGUgSW5jLjETMBEGA1UECAwKQ2FsaWZvcm5pYTAeFw0yMDAzMTgxODMyNTNa
Fw00NTAzMTUwMDAwMDBaMFIxJjAkBgNVBAMMHUFwcGxlIEFwcCBBdHRlc3RhdGlv
biBSb290IENBMRMwEQYDVQQKDApBcHBsZSBJbmMuMRMwEQYDVQQIDApDYWxpZm9y
bmlhMHYwEAYHKoZIzj0CAQYFK4EEACIDYgAERTHhmLW07ATaFQIEVwTtT4dyctdh
NbJhFs/Ii2FdCgAHGbpphY3+d8qjuDngIN3WVhQUBHAoMeQ/cLiP1sOUtgjqK9au
Yen1mMEvRq9Sk3Jm5X8U62H+xTD3FE9TgS41o0IwQDAPBgNVHRMBAf8EBTADAQH/
MB0GA1UdDgQWBBSskRBTM72+aEH/pwyp5frq5eWKoTAOBgNVHQ8BAf8EBAMCAQYw
CgYIKoZIzj0EAwMDaAAwZQIwQgFGnByvsiVbpTKwSga0kP0e8EeDS4+sQmTvb7vn
53O5+FRXgeLhpJ06ysC5PrOyAjEAp5U4xDgEgllF7En3VcE3iexZZtKeYnpqtijV
oyFraWVIyd/dganmrduC1bmTBGwD
-----END CERTIFICATE-----"""

_google_credentials: Any | None = None


class AppIntegrityVerifierUnavailable(Exception):
    pass


@dataclass(frozen=True)
class IosAttestationVerification:
    public_key_pem: str
    receipt_b64: str | None
    environment: str


def _mode() -> str:
    return APP_INTEGRITY_MODE if APP_INTEGRITY_MODE in APP_INTEGRITY_MODES else "enforce"


def _csv_values(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _decode_base64(value: str) -> bytes:
    normalized = value.strip()
    padding = "=" * (-len(normalized) % 4)
    return base64.urlsafe_b64decode(f"{normalized}{padding}")


def _encode_base64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _public_key_x962_hash(public_key: ec.EllipticCurvePublicKey) -> str:
    public_key_bytes = public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return _encode_base64(_sha256(public_key_bytes))


def _is_truthy_verdict(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("ok") or payload.get("valid") or payload.get("allow"))


def _ios_app_id() -> str | None:
    if not APP_INTEGRITY_IOS_TEAM_ID or not APP_INTEGRITY_IOS_BUNDLE_ID:
        return None
    return f"{APP_INTEGRITY_IOS_TEAM_ID}.{APP_INTEGRITY_IOS_BUNDLE_ID}"


def _ios_allowed_environments() -> set[str]:
    return _csv_values(APP_INTEGRITY_IOS_ALLOWED_ENVIRONMENTS) or {"production"}


def _ios_environment_from_aaguid(aaguid: bytes) -> str | None:
    for environment, expected_aaguid in APPLE_APP_ATTEST_AAGUIDS.items():
        if hmac.compare_digest(aaguid, expected_aaguid):
            return environment
    return None


def _parse_authenticator_data(auth_data: bytes, *, require_attested_credential_data: bool) -> dict[str, Any]:
    if len(auth_data) < 37:
        raise ValueError("authenticator data is too short")

    parsed: dict[str, Any] = {
        "rp_id_hash": auth_data[:32],
        "flags": auth_data[32],
        "counter": int.from_bytes(auth_data[33:37], "big"),
    }

    if not require_attested_credential_data:
        return parsed

    if len(auth_data) < 55:
        raise ValueError("attestation authenticator data is too short")

    credential_id_length = int.from_bytes(auth_data[53:55], "big")
    credential_id_start = 55
    credential_id_end = credential_id_start + credential_id_length
    if len(auth_data) < credential_id_end:
        raise ValueError("attestation credential id is truncated")

    parsed.update(
        {
            "aaguid": auth_data[37:53],
            "credential_id": auth_data[credential_id_start:credential_id_end],
        }
    )
    return parsed


def _verify_cert_signed_by(child: x509.Certificate, issuer: x509.Certificate) -> None:
    issuer_public_key = issuer.public_key()
    if not isinstance(issuer_public_key, ec.EllipticCurvePublicKey):
        raise ValueError("unsupported App Attest issuer public key")
    issuer_public_key.verify(
        child.signature,
        child.tbs_certificate_bytes,
        ec.ECDSA(child.signature_hash_algorithm),
    )


def _verify_app_attest_cert_chain(leaf: x509.Certificate, intermediate: x509.Certificate) -> None:
    root = x509.load_pem_x509_certificate(APPLE_APP_ATTEST_ROOT_CA_PEM)
    now = ufa_now()

    for cert in (leaf, intermediate, root):
        if hasattr(cert, "not_valid_before_utc"):
            not_valid_before = cert.not_valid_before_utc
            not_valid_after = cert.not_valid_after_utc
        else:
            not_valid_before = cert.not_valid_before.replace(tzinfo=timezone.utc)
            not_valid_after = cert.not_valid_after.replace(tzinfo=timezone.utc)
        if now < not_valid_before or now > not_valid_after:
            raise ValueError("App Attest certificate is outside validity window")

    if leaf.issuer != intermediate.subject or intermediate.issuer != root.subject:
        raise ValueError("App Attest certificate issuer mismatch")

    _verify_cert_signed_by(leaf, intermediate)
    _verify_cert_signed_by(intermediate, root)

    intermediate_constraints = intermediate.extensions.get_extension_for_oid(
        ExtensionOID.BASIC_CONSTRAINTS
    ).value
    if not intermediate_constraints.ca:
        raise ValueError("App Attest intermediate is not a CA")


def _extract_app_attest_nonce(leaf: x509.Certificate) -> bytes:
    extension = leaf.extensions.get_extension_for_oid(APPLE_APP_ATTEST_NONCE_OID)
    decoded, remainder = der_decoder.decode(extension.value.value)
    if remainder:
        raise ValueError("App Attest nonce extension has trailing data")
    return bytes(decoded[0])


def _verify_ios_attestation_object(*, key_id: str, challenge: str, attestation_object_b64: str) -> IosAttestationVerification:
    app_id = _ios_app_id()
    if app_id is None:
        raise ValueError("iOS App Attest app id is not configured")

    key_id_bytes = _decode_base64(key_id)
    attestation_object = cbor2.loads(_decode_base64(attestation_object_b64))
    if not isinstance(attestation_object, dict) or attestation_object.get("fmt") != "apple-appattest":
        raise ValueError("invalid App Attest attestation object")

    att_stmt = attestation_object.get("attStmt")
    auth_data = attestation_object.get("authData")
    if not isinstance(att_stmt, dict) or not isinstance(auth_data, bytes):
        raise ValueError("invalid App Attest attestation payload")

    x5c = att_stmt.get("x5c")
    if not isinstance(x5c, list) or len(x5c) < 2 or not all(isinstance(cert, bytes) for cert in x5c[:2]):
        raise ValueError("invalid App Attest certificate chain")

    leaf = x509.load_der_x509_certificate(x5c[0])
    intermediate = x509.load_der_x509_certificate(x5c[1])
    _verify_app_attest_cert_chain(leaf, intermediate)

    client_data_hash = _sha256(challenge.encode("utf-8"))
    expected_nonce = _sha256(auth_data + client_data_hash)
    if not hmac.compare_digest(_extract_app_attest_nonce(leaf), expected_nonce):
        raise ValueError("App Attest nonce mismatch")

    public_key = leaf.public_key()
    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise ValueError("App Attest public key is not EC")
    if not hmac.compare_digest(_decode_base64(_public_key_x962_hash(public_key)), key_id_bytes):
        raise ValueError("App Attest key id mismatch")

    parsed_auth_data = _parse_authenticator_data(auth_data, require_attested_credential_data=True)
    if not hmac.compare_digest(parsed_auth_data["rp_id_hash"], _sha256(app_id.encode("utf-8"))):
        raise ValueError("App Attest RP ID mismatch")
    if parsed_auth_data["counter"] != 0:
        raise ValueError("App Attest initial counter is not zero")
    if not hmac.compare_digest(parsed_auth_data["credential_id"], key_id_bytes):
        raise ValueError("App Attest credential id mismatch")

    environment = _ios_environment_from_aaguid(parsed_auth_data["aaguid"])
    if environment is None or environment not in _ios_allowed_environments():
        raise ValueError("App Attest environment mismatch")

    receipt = att_stmt.get("receipt")
    public_key_pem = public_key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return IosAttestationVerification(
        public_key_pem=public_key_pem,
        receipt_b64=_encode_base64(receipt) if isinstance(receipt, bytes) else None,
        environment=environment,
    )


def _google_access_token_sync() -> str:
    global _google_credentials

    if _google_credentials is None:
        _google_credentials, _ = google.auth.default(scopes=[PLAY_INTEGRITY_SCOPE])

    if not _google_credentials.valid or _google_credentials.expired or not _google_credentials.token:
        _google_credentials.refresh(GoogleAuthRequest())

    return _google_credentials.token


async def _get_google_access_token() -> str:
    try:
        return await to_thread.run_sync(_google_access_token_sync)
    except GoogleAuthError as exc:
        raise AppIntegrityVerifierUnavailable("google credentials unavailable") from exc


async def _decode_android_integrity_token(token: str) -> dict[str, Any]:
    if not APP_INTEGRITY_ANDROID_PACKAGE_NAME:
        raise AppIntegrityVerifierUnavailable("android package not configured")

    access_token = await _get_google_access_token()
    package_name = quote(APP_INTEGRITY_ANDROID_PACKAGE_NAME, safe="")
    url = f"https://playintegrity.googleapis.com/v1/{package_name}:decodeIntegrityToken"
    try:
        async with httpx.AsyncClient(timeout=APP_INTEGRITY_VERIFIER_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json={"integrity_token": token},
            )
    except httpx.HTTPError as exc:
        raise AppIntegrityVerifierUnavailable("google play integrity request failed") from exc

    if response.status_code >= 500:
        raise AppIntegrityVerifierUnavailable("google play integrity service unavailable")
    if response.status_code >= 400:
        log.warning(
            "Google Play Integrity rejected token status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        return {}

    return response.json()


def _is_android_payload_fresh(timestamp_millis: Any) -> bool:
    try:
        token_timestamp = int(timestamp_millis) / 1000
    except (TypeError, ValueError):
        return False

    age_seconds = time.time() - token_timestamp
    return -30 <= age_seconds <= APP_INTEGRITY_TOKEN_MAX_AGE_SECONDS


async def _verify_android_play_integrity(token: str, request_hash: str) -> tuple[bool, str | None]:
    if not APP_INTEGRITY_ANDROID_PACKAGE_NAME:
        return False, "android package not configured"

    payload = (await _decode_android_integrity_token(token)).get("tokenPayloadExternal")
    if not isinstance(payload, dict):
        return False, "empty google verdict"

    request_details = payload.get("requestDetails") if isinstance(payload.get("requestDetails"), dict) else {}
    app_integrity = payload.get("appIntegrity") if isinstance(payload.get("appIntegrity"), dict) else {}
    device_integrity = payload.get("deviceIntegrity") if isinstance(payload.get("deviceIntegrity"), dict) else {}

    if request_details.get("requestPackageName") != APP_INTEGRITY_ANDROID_PACKAGE_NAME:
        return False, "android request package mismatch"
    if request_details.get("requestHash") != request_hash:
        return False, "android request hash mismatch"
    if not _is_android_payload_fresh(request_details.get("timestampMillis")):
        return False, "android token expired"

    if app_integrity.get("appRecognitionVerdict") != "PLAY_RECOGNIZED":
        return False, "android app not play recognized"
    if app_integrity.get("packageName") != APP_INTEGRITY_ANDROID_PACKAGE_NAME:
        return False, "android app package mismatch"

    allowed_cert_digests = _csv_values(APP_INTEGRITY_ANDROID_CERT_SHA256_DIGESTS)
    verdict_cert_digests = set(app_integrity.get("certificateSha256Digest") or [])
    if not allowed_cert_digests:
        return False, "android cert digests not configured"
    if not allowed_cert_digests.intersection(verdict_cert_digests):
        return False, "android cert digest mismatch"

    allowed_device_verdicts = _csv_values(APP_INTEGRITY_ANDROID_ALLOWED_DEVICE_VERDICTS)
    verdict_device_labels = set(device_integrity.get("deviceRecognitionVerdict") or [])
    if allowed_device_verdicts and not allowed_device_verdicts.intersection(verdict_device_labels):
        return False, "android device integrity failed"

    return True, None


async def create_app_integrity_challenge(
    db: AsyncSession,
    *,
    user_id: int,
    platform: str,
    purpose: str,
    action: str | None = None,
) -> AppIntegrityChallenge:
    challenge = AppIntegrityChallenge(
        user_id=user_id,
        challenge=secrets.token_urlsafe(32),
        platform=platform,
        purpose=purpose,
        action=action,
        expires_at=ufa_now() + timedelta(seconds=APP_INTEGRITY_CHALLENGE_TTL_SECONDS),
    )
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)
    return challenge


async def _consume_app_integrity_challenge(
    db: AsyncSession,
    *,
    user_id: int,
    platform: str,
    purpose: str,
    challenge: str,
    action: str | None = None,
) -> AppIntegrityChallenge | None:
    stmt = (
        select(AppIntegrityChallenge)
        .where(
            AppIntegrityChallenge.user_id == user_id,
            AppIntegrityChallenge.platform == platform,
            AppIntegrityChallenge.purpose == purpose,
            AppIntegrityChallenge.challenge == challenge,
            AppIntegrityChallenge.consumed_at.is_(None),
            AppIntegrityChallenge.expires_at > ufa_now(),
        )
        .with_for_update()
    )
    if action is None:
        stmt = stmt.where(AppIntegrityChallenge.action.is_(None))
    else:
        stmt = stmt.where(AppIntegrityChallenge.action == action)

    challenge_record = (await db.execute(stmt)).scalar_one_or_none()
    if challenge_record is None:
        return None

    challenge_record.consumed_at = ufa_now()
    return challenge_record


async def register_ios_app_attest_key(
    db: AsyncSession,
    *,
    user_id: int,
    key_id: str,
    challenge: str,
    attestation_object: str,
) -> AppAttestKey:
    challenge_record = await _consume_app_integrity_challenge(
        db,
        user_id=user_id,
        platform="ios",
        purpose="attestation",
        challenge=challenge,
    )
    if challenge_record is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid App Attest challenge")

    await db.commit()

    try:
        verification = _verify_ios_attestation_object(
            key_id=key_id,
            challenge=challenge,
            attestation_object_b64=attestation_object,
        )
    except (ValueError, cbor2.CBORDecodeError) as exc:
        log.warning("iOS App Attest registration rejected user_id=%s reason=%s", user_id, exc)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="App Attest verification failed") from exc

    existing_key = (
        await db.execute(
            select(AppAttestKey)
            .where(AppAttestKey.key_id == key_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing_key is not None and existing_key.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="App Attest key is already registered")

    if existing_key is None:
        app_attest_key = AppAttestKey(
            user_id=user_id,
            key_id=key_id,
            public_key_pem=verification.public_key_pem,
            receipt_b64=verification.receipt_b64,
            environment=verification.environment,
            counter=0,
            is_active=True,
        )
        db.add(app_attest_key)
    else:
        app_attest_key = existing_key
        app_attest_key.public_key_pem = verification.public_key_pem
        app_attest_key.receipt_b64 = verification.receipt_b64
        app_attest_key.environment = verification.environment
        app_attest_key.counter = 0
        app_attest_key.is_active = True

    await db.commit()
    await db.refresh(app_attest_key)
    return app_attest_key


def _verify_ios_assertion_signature(
    *,
    public_key_pem: str,
    challenge: str,
    assertion_b64: str,
    key_id: str | None = None,
) -> int:
    app_id = _ios_app_id()
    if app_id is None:
        raise ValueError("iOS App Attest app id is not configured")

    assertion = cbor2.loads(_decode_base64(assertion_b64))
    if not isinstance(assertion, dict):
        raise ValueError("invalid App Attest assertion object")

    signature = assertion.get("signature")
    auth_data = assertion.get("authenticatorData")
    if not isinstance(signature, bytes) or not isinstance(auth_data, bytes):
        raise ValueError("invalid App Attest assertion payload")

    parsed_auth_data = _parse_authenticator_data(auth_data, require_attested_credential_data=False)
    expected_rp_id_hash = _sha256(app_id.encode("utf-8"))
    if not hmac.compare_digest(parsed_auth_data["rp_id_hash"], expected_rp_id_hash):
        raise ValueError("App Attest assertion RP ID mismatch")

    public_key = serialization.load_pem_public_key(public_key_pem.encode("ascii"))
    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise ValueError("App Attest assertion public key is not EC")

    client_data_hash = _sha256(challenge.encode("utf-8"))
    nonce = _sha256(auth_data + client_data_hash)
    public_key_matches_key_id: bool | str | None = None
    if key_id:
        try:
            public_key_matches_key_id = hmac.compare_digest(
                _decode_base64(_public_key_x962_hash(public_key)),
                _decode_base64(key_id),
            )
        except (ValueError, TypeError) as exc:
            public_key_matches_key_id = f"decode_error:{exc}"

    if public_key_matches_key_id is False:
        raise ValueError("stored App Attest public key does not match key id")

    signature_variants: list[tuple[str, bytes]] = [("der", signature)]
    if len(signature) == 64:
        signature_variants.append(
            (
                "raw-rs-as-der",
                asymmetric_utils.encode_dss_signature(
                    int.from_bytes(signature[:32], "big"),
                    int.from_bytes(signature[32:], "big"),
                ),
            )
        )

    verification_attempts: list[tuple[str, bytes, ec.ECDSA]] = [
        ("nonce_prehashed", nonce, ec.ECDSA(asymmetric_utils.Prehashed(hashes.SHA256()))),
        ("auth_data_plus_client_hash_sha256", auth_data + client_data_hash, ec.ECDSA(hashes.SHA256())),
        ("nonce_sha256", nonce, ec.ECDSA(hashes.SHA256())),
    ]
    failed_attempts: list[str] = []

    for signature_label, signature_variant in signature_variants:
        for attempt_label, signed_data, algorithm in verification_attempts:
            try:
                public_key.verify(signature_variant, signed_data, algorithm)
                return parsed_auth_data["counter"]
            except (InvalidSignature, ValueError) as exc:
                failed_attempts.append(f"{signature_label}/{attempt_label}:{type(exc).__name__}")

    raise ValueError(
        "invalid App Attest assertion signature "
        f"signature_len={len(signature)} auth_data_len={len(auth_data)} "
        f"counter={parsed_auth_data['counter']} attempts={'|'.join(failed_attempts)}"
    )


async def _verify_ios_app_attest_assertion(
    db: AsyncSession,
    *,
    user_id: int,
    key_id: str | None,
    assertion: str,
    challenge: str,
    action: str,
) -> tuple[bool, str | None]:
    if not key_id:
        return False, "missing iOS key id"

    challenge_record = await _consume_app_integrity_challenge(
        db,
        user_id=user_id,
        platform="ios",
        purpose="assertion",
        challenge=challenge,
        action=action,
    )
    if challenge_record is None:
        return False, "invalid iOS challenge"

    await db.commit()

    app_attest_key = (
        await db.execute(
            select(AppAttestKey)
            .where(
                AppAttestKey.user_id == user_id,
                AppAttestKey.key_id == key_id,
                AppAttestKey.is_active.is_(True),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if app_attest_key is None:
        return False, "unregistered iOS key"

    try:
        assertion_counter = _verify_ios_assertion_signature(
            public_key_pem=app_attest_key.public_key_pem,
            challenge=challenge,
            assertion_b64=assertion,
            key_id=key_id,
        )
    except ValueError as exc:
        log.warning("iOS App Attest assertion rejected user_id=%s reason=%s", user_id, exc)
        return False, "invalid iOS assertion"
    except InvalidSignature:
        log.warning("iOS App Attest assertion rejected user_id=%s reason=invalid signature", user_id)
        return False, "invalid iOS assertion"
    except cbor2.CBORDecodeError as exc:
        log.warning("iOS App Attest assertion rejected user_id=%s reason=invalid cbor: %s", user_id, exc)
        return False, "invalid iOS assertion"

    if assertion_counter <= app_attest_key.counter:
        return False, "stale iOS assertion counter"

    app_attest_key.counter = assertion_counter
    await db.commit()
    return True, None


async def _verify_with_remote_service(request: Request, *, action: str, token: str, platform: str, request_hash: str) -> bool:
    if not APP_INTEGRITY_VERIFIER_URL:
        return False

    body = {
        "token": token,
        "platform": platform,
        "action": action,
        "request_hash": request_hash,
        "key_id": request.headers.get(APP_INTEGRITY_KEY_ID_HEADER),
        "path": request.url.path,
        "method": request.method,
    }
    async with httpx.AsyncClient(timeout=APP_INTEGRITY_VERIFIER_TIMEOUT_SECONDS) as client:
        response = await client.post(APP_INTEGRITY_VERIFIER_URL, json=body)
        response.raise_for_status()
        return _is_truthy_verdict(response.json())


async def verify_app_integrity_request(
    request: Request,
    *,
    action: str,
    db: AsyncSession | None = None,
    current_user: User | None = None,
) -> None:
    mode = _mode()
    if mode == "off":
        return

    token = (request.headers.get(APP_INTEGRITY_TOKEN_HEADER) or "").strip()
    platform = (request.headers.get(APP_INTEGRITY_PLATFORM_HEADER) or "").strip().lower()
    header_action = (request.headers.get(APP_INTEGRITY_ACTION_HEADER) or "").strip()
    request_hash = (request.headers.get(APP_INTEGRITY_REQUEST_HASH_HEADER) or "").strip()
    key_id = (request.headers.get(APP_INTEGRITY_KEY_ID_HEADER) or "").strip()

    reason: str | None = None
    verified = False

    if not token:
        reason = "missing token"
    elif platform not in {"ios", "android"}:
        reason = "unsupported platform"
    elif header_action != action:
        reason = "action mismatch"
    elif not request_hash:
        reason = "missing request hash"
    elif APP_INTEGRITY_DEV_TOKEN and hmac.compare_digest(token, APP_INTEGRITY_DEV_TOKEN):
        verified = True
    else:
        try:
            if platform == "android" and APP_INTEGRITY_ANDROID_PACKAGE_NAME:
                verified, reason = await _verify_android_play_integrity(token, request_hash)
            elif platform == "ios" and APP_INTEGRITY_IOS_TEAM_ID and APP_INTEGRITY_IOS_BUNDLE_ID:
                if db is None or current_user is None:
                    reason = "missing iOS verifier context"
                else:
                    verified, reason = await _verify_ios_app_attest_assertion(
                        db,
                        user_id=current_user.id,
                        key_id=key_id,
                        assertion=token,
                        challenge=request_hash,
                        action=action,
                    )
            else:
                verified = await _verify_with_remote_service(
                    request,
                    action=action,
                    token=token,
                    platform=platform,
                    request_hash=request_hash,
                )
                if not verified and reason is None:
                    reason = "verifier rejected token"
        except (AppIntegrityVerifierUnavailable, httpx.HTTPError):
            log.exception("App integrity verifier unavailable action=%s path=%s", action, request.url.path)
            if mode == "enforce":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="App integrity verifier is unavailable",
                )
            reason = "verifier unavailable"

    if verified:
        return

    log.warning(
        "App integrity check failed mode=%s action=%s path=%s platform=%s reason=%s",
        mode,
        action,
        request.url.path,
        platform or None,
        reason,
    )
    if mode == "enforce":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="App integrity check failed")


def require_app_integrity(action: str):
    async def dependency(
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> None:
        await verify_app_integrity_request(request, action=action, db=db, current_user=current_user)

    return dependency
