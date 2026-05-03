import hmac
import logging
import secrets
import time
import cbor2
import google.auth
import httpx

from datetime import timedelta
from typing import Any
from urllib.parse import quote
from anyio import to_thread
from fastapi import Depends, HTTPException, Request
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleAuthRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import ufa_now
from src.app.modules.auth.dependencies import get_current_user
from src.database import get_db
from src.database.models import AppAttestKey, AppIntegrityChallenge, User

from .common import csv_values, is_truthy_verdict, mode
from .constants import (
    APP_INTEGRITY_ACTION_HEADER,
    APP_INTEGRITY_ANDROID_ALLOWED_DEVICE_VERDICTS,
    APP_INTEGRITY_ANDROID_CERT_SHA256_DIGESTS,
    APP_INTEGRITY_ANDROID_PACKAGE_NAME,
    APP_INTEGRITY_CHALLENGE_TTL_SECONDS,
    APP_INTEGRITY_DEV_TOKEN,
    APP_INTEGRITY_IOS_BUNDLE_ID,
    APP_INTEGRITY_IOS_TEAM_ID,
    APP_INTEGRITY_KEY_ID_HEADER,
    APP_INTEGRITY_PLATFORM_HEADER,
    APP_INTEGRITY_REQUEST_HASH_HEADER,
    APP_INTEGRITY_TOKEN_HEADER,
    APP_INTEGRITY_TOKEN_MAX_AGE_SECONDS,
    APP_INTEGRITY_VERIFIER_TIMEOUT_SECONDS,
    APP_INTEGRITY_VERIFIER_URL,
    PLAY_INTEGRITY_SCOPE,
)
from .ios_verifier import verify_ios_assertion_signature, verify_ios_attestation_object
from .types import AppIntegrityVerifierUnavailable

log = logging.getLogger(__name__)

_google_credentials: Any | None = None


def _google_access_token_sync() -> str:
    global _google_credentials
    if _google_credentials is None: _google_credentials, _ = google.auth.default(scopes=[PLAY_INTEGRITY_SCOPE])
    if not _google_credentials.valid or _google_credentials.expired or not _google_credentials.token: _google_credentials.refresh(GoogleAuthRequest())
    return _google_credentials.token


async def _get_google_access_token() -> str:
    try: return await to_thread.run_sync(_google_access_token_sync)
    except GoogleAuthError as exc: raise AppIntegrityVerifierUnavailable("google credentials unavailable") from exc


async def _decode_android_integrity_token(token: str) -> dict[str, Any]:
    if not APP_INTEGRITY_ANDROID_PACKAGE_NAME: raise AppIntegrityVerifierUnavailable("android package not configured")
    access_token = await _get_google_access_token()
    package_name = quote(APP_INTEGRITY_ANDROID_PACKAGE_NAME, safe="")
    url = f"https://playintegrity.googleapis.com/v1/{package_name}:decodeIntegrityToken"

    try:
        async with httpx.AsyncClient(timeout=APP_INTEGRITY_VERIFIER_TIMEOUT_SECONDS) as client: response = await client.post(url, headers={"Authorization": f"Bearer {access_token}"}, json={"integrity_token": token})
    except httpx.HTTPError as exc: raise AppIntegrityVerifierUnavailable("google play integrity request failed") from exc

    if response.status_code >= 500: raise AppIntegrityVerifierUnavailable("google play integrity service unavailable")
    if response.status_code >= 400:
        log.warning("Google Play Integrity rejected token status=%s body=%s", response.status_code, response.text[:500])
        return {}

    return response.json()


def _is_android_payload_fresh(timestamp_millis: Any) -> bool:
    try: token_timestamp = int(timestamp_millis) / 1000
    except (TypeError, ValueError): return False
    age_seconds = time.time() - token_timestamp
    return -30 <= age_seconds <= APP_INTEGRITY_TOKEN_MAX_AGE_SECONDS


async def _verify_android_play_integrity(token: str, request_hash: str) -> tuple[bool, str | None]:
    if not APP_INTEGRITY_ANDROID_PACKAGE_NAME: return False, "android package not configured"
    payload = (await _decode_android_integrity_token(token)).get("tokenPayloadExternal")
    if not isinstance(payload, dict): return False, "empty google verdict"

    request_details = payload.get("requestDetails") if isinstance(payload.get("requestDetails"), dict) else {}
    app_integrity = payload.get("appIntegrity") if isinstance(payload.get("appIntegrity"), dict) else {}
    device_integrity = payload.get("deviceIntegrity") if isinstance(payload.get("deviceIntegrity"), dict) else {}

    if request_details.get("requestPackageName") != APP_INTEGRITY_ANDROID_PACKAGE_NAME: return False, "android request package mismatch"
    if request_details.get("requestHash") != request_hash: return False, "android request hash mismatch"
    if not _is_android_payload_fresh(request_details.get("timestampMillis")): return False, "android token expired"

    if app_integrity.get("appRecognitionVerdict") != "PLAY_RECOGNIZED": return False, "android app not play recognized"
    if app_integrity.get("packageName") != APP_INTEGRITY_ANDROID_PACKAGE_NAME: return False, "android app package mismatch"

    allowed_cert_digests = csv_values(APP_INTEGRITY_ANDROID_CERT_SHA256_DIGESTS)
    verdict_cert_digests = set(app_integrity.get("certificateSha256Digest") or [])
    if not allowed_cert_digests: return False, "android cert digests not configured"
    if not allowed_cert_digests.intersection(verdict_cert_digests): return False, "android cert digest mismatch"

    allowed_device_verdicts = csv_values(APP_INTEGRITY_ANDROID_ALLOWED_DEVICE_VERDICTS)
    verdict_device_labels = set(device_integrity.get("deviceRecognitionVerdict") or [])
    if allowed_device_verdicts and not allowed_device_verdicts.intersection(verdict_device_labels): return False, "android device integrity failed"

    return True, None


async def create_app_integrity_challenge(db: AsyncSession, *, user_id: int, platform: str, purpose: str, action: str | None = None) -> AppIntegrityChallenge:
    challenge = AppIntegrityChallenge(user_id=user_id, challenge=secrets.token_urlsafe(32), platform=platform, purpose=purpose, action=action, expires_at=ufa_now() + timedelta(seconds=APP_INTEGRITY_CHALLENGE_TTL_SECONDS))
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)
    return challenge


async def _consume_app_integrity_challenge(db: AsyncSession, *, user_id: int, platform: str, purpose: str, challenge: str, action: str | None = None) -> AppIntegrityChallenge | None:
    stmt = (select(AppIntegrityChallenge).where(AppIntegrityChallenge.user_id == user_id, AppIntegrityChallenge.platform == platform, AppIntegrityChallenge.purpose == purpose, AppIntegrityChallenge.challenge == challenge, AppIntegrityChallenge.consumed_at.is_(None), AppIntegrityChallenge.expires_at > ufa_now()).with_for_update())
    if action is None: stmt = stmt.where(AppIntegrityChallenge.action.is_(None))
    else: stmt = stmt.where(AppIntegrityChallenge.action == action)

    challenge_record = (await db.execute(stmt)).scalar_one_or_none()
    if challenge_record is None: return None

    challenge_record.consumed_at = ufa_now()
    return challenge_record


async def register_ios_app_attest_key(db: AsyncSession, *, user_id: int, key_id: str, challenge: str, attestation_object: str) -> AppAttestKey:
    challenge_record = await _consume_app_integrity_challenge(db, user_id=user_id, platform="ios", purpose="attestation", challenge=challenge)
    if challenge_record is None: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid App Attest challenge")

    await db.commit()

    try: verification = verify_ios_attestation_object(key_id=key_id, challenge=challenge, attestation_object_b64=attestation_object)
    except (ValueError, cbor2.CBORDecodeError) as exc:
        log.warning("iOS App Attest registration rejected user_id=%s reason=%s", user_id, exc)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="App Attest verification failed") from exc

    existing_key = (await db.execute(select(AppAttestKey).where(AppAttestKey.key_id == key_id).with_for_update())).scalar_one_or_none()
    if existing_key is not None and existing_key.user_id != user_id: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="App Attest key is already registered")

    if existing_key is None:
        app_attest_key = AppAttestKey(user_id=user_id, key_id=key_id, public_key_pem=verification.public_key_pem, receipt_b64=verification.receipt_b64, environment=verification.environment, counter=0, is_active=True)
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


async def _verify_ios_app_attest_assertion(db: AsyncSession, *, user_id: int, key_id: str | None, assertion: str, challenge: str, action: str) -> tuple[bool, str | None]:
    if not key_id: return False, "missing iOS key id"

    challenge_record = await _consume_app_integrity_challenge(db, user_id=user_id, platform="ios", purpose="assertion", challenge=challenge, action=action)
    if challenge_record is None: return False, "invalid iOS challenge"

    await db.commit()
    app_attest_key = (await db.execute(select(AppAttestKey).where(AppAttestKey.user_id == user_id, AppAttestKey.key_id == key_id,AppAttestKey.is_active.is_(True)).with_for_update())).scalar_one_or_none()
    if app_attest_key is None: return False, "unregistered iOS key"

    try: assertion_counter = verify_ios_assertion_signature( public_key_pem=app_attest_key.public_key_pem, challenge=challenge, assertion_b64=assertion, key_id=key_id)
    except ValueError as exc:
        log.warning("iOS App Attest assertion rejected user_id=%s reason=%s", user_id, exc)
        return False, "invalid iOS assertion"

    except cbor2.CBORDecodeError as exc:
        log.warning("iOS App Attest assertion rejected user_id=%s reason=invalid cbor: %s", user_id, exc)
        return False, "invalid iOS assertion"

    if assertion_counter <= app_attest_key.counter: return False, "stale iOS assertion counter"
    app_attest_key.counter = assertion_counter
    await db.commit()
    return True, None


async def _verify_with_remote_service(request: Request, *, action: str, token: str, platform: str, request_hash: str) -> bool:
    if not APP_INTEGRITY_VERIFIER_URL: return False
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
        return is_truthy_verdict(response.json())


async def verify_app_integrity_request(request: Request, *, action: str, db: AsyncSession | None = None, current_user: User | None = None) -> None:
    app_integrity_mode = mode()
    if app_integrity_mode == "off": return

    token = (request.headers.get(APP_INTEGRITY_TOKEN_HEADER) or "").strip()
    platform = (request.headers.get(APP_INTEGRITY_PLATFORM_HEADER) or "").strip().lower()
    header_action = (request.headers.get(APP_INTEGRITY_ACTION_HEADER) or "").strip()
    request_hash = (request.headers.get(APP_INTEGRITY_REQUEST_HASH_HEADER) or "").strip()
    key_id = (request.headers.get(APP_INTEGRITY_KEY_ID_HEADER) or "").strip()

    reason: str | None = None
    verified = False

    if not token: reason = "missing token"
    elif platform not in {"ios", "android"}: reason = "unsupported platform"
    elif header_action != action: reason = "action mismatch"
    elif not request_hash: reason = "missing request hash"
    elif APP_INTEGRITY_DEV_TOKEN and hmac.compare_digest(token, APP_INTEGRITY_DEV_TOKEN): verified = True
    else:
        try:
            if platform == "android" and APP_INTEGRITY_ANDROID_PACKAGE_NAME: verified, reason = await _verify_android_play_integrity(token, request_hash)
            elif platform == "ios" and APP_INTEGRITY_IOS_TEAM_ID and APP_INTEGRITY_IOS_BUNDLE_ID:
                if db is None or current_user is None: reason = "missing iOS verifier context"
                else: verified, reason = await _verify_ios_app_attest_assertion( db, user_id=current_user.id, key_id=key_id, assertion=token, challenge=request_hash, action=action)

            else:
                verified = await _verify_with_remote_service(request, action=action, token=token, platform=platform, request_hash=request_hash)
                if not verified and reason is None: reason = "verifier rejected token"

        except (AppIntegrityVerifierUnavailable, httpx.HTTPError):
            log.exception("App integrity verifier unavailable action=%s path=%s", action, request.url.path)
            if app_integrity_mode == "enforce": raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="App integrity verifier is unavailable")
            reason = "verifier unavailable"

    if verified: return
    log.warning("App integrity check failed mode=%s action=%s path=%s platform=%s reason=%s", app_integrity_mode, action, request.url.path, platform or None, reason)
    if app_integrity_mode == "enforce": raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="App integrity check failed")


def require_app_integrity(action: str):
    async def dependency(request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> None: await verify_app_integrity_request(request, action=action, db=db, current_user=current_user)
    return dependency
