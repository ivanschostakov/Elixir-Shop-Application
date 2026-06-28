import time

import pytest
from fastapi import HTTPException
from types import SimpleNamespace
from starlette.requests import Request

import src.app.services.app_integrity.common as app_integrity_common
import src.app.services.app_integrity.service as app_integrity
from src.app.services.app_integrity.types import IosAttestationVerification


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeDb:
    def __init__(self, execute_results: list | None = None):
        self.execute_results = execute_results or []
        self.added = []
        self.commits = 0
        self.refreshed = []

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        self.refreshed.append(value)

    async def execute(self, _stmt):
        return _ScalarResult(self.execute_results.pop(0) if self.execute_results else None)


def _request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/users/me/orders",
            "headers": raw_headers,
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )


def _integrity_headers(
    *,
    action: str = "orders:create",
    token: str = "dev-token",
    platform: str = "ios",
    request_hash: str = "test-request-hash",
    key_id: str | None = None,
) -> dict[str, str]:
    headers = {
        app_integrity.APP_INTEGRITY_ACTION_HEADER: action,
        app_integrity.APP_INTEGRITY_PLATFORM_HEADER: platform,
        app_integrity.APP_INTEGRITY_REQUEST_HASH_HEADER: request_hash,
        app_integrity.APP_INTEGRITY_TOKEN_HEADER: token,
    }
    if key_id:
        headers[app_integrity.APP_INTEGRITY_KEY_ID_HEADER] = key_id
    return headers


def _android_verdict(*, request_hash: str = "test-request-hash", package_name: str = "com.example.app") -> dict:
    return {
        "tokenPayloadExternal": {
            "requestDetails": {
                "requestPackageName": package_name,
                "requestHash": request_hash,
                "timestampMillis": str(int(time.time() * 1000)),
            },
            "appIntegrity": {
                "appRecognitionVerdict": "PLAY_RECOGNIZED",
                "packageName": package_name,
                "certificateSha256Digest": ["cert-digest"],
                "versionCode": "1",
            },
            "deviceIntegrity": {
                "deviceRecognitionVerdict": ["MEETS_DEVICE_INTEGRITY"],
            },
        }
    }


@pytest.mark.anyio
async def test_app_integrity_enforce_rejects_missing_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_integrity_common, "APP_INTEGRITY_MODE", "enforce")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_DEV_TOKEN", "dev-token")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_VERIFIER_URL", None)

    with pytest.raises(HTTPException) as exc_info:
        await app_integrity.verify_app_integrity_request(_request(), action="orders:create")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "App integrity check failed"


@pytest.mark.anyio
async def test_app_integrity_enforce_accepts_dev_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_integrity_common, "APP_INTEGRITY_MODE", "enforce")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_DEV_TOKEN", "dev-token")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_VERIFIER_URL", None)

    await app_integrity.verify_app_integrity_request(
        _request(_integrity_headers()),
        action="orders:create",
    )


@pytest.mark.anyio
async def test_app_integrity_enforce_rejects_action_mismatch(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_integrity_common, "APP_INTEGRITY_MODE", "enforce")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_DEV_TOKEN", "dev-token")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_VERIFIER_URL", None)

    with pytest.raises(HTTPException) as exc_info:
        await app_integrity.verify_app_integrity_request(
            _request(_integrity_headers(action="payments:create")),
            action="orders:create",
        )

    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_app_integrity_monitor_does_not_reject(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_integrity_common, "APP_INTEGRITY_MODE", "monitor")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_DEV_TOKEN", None)
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_VERIFIER_URL", None)

    await app_integrity.verify_app_integrity_request(_request(), action="orders:create")


@pytest.mark.anyio
async def test_app_integrity_enforce_accepts_google_verified_android_token(monkeypatch: pytest.MonkeyPatch):
    async def fake_decode_android_integrity_token(_token: str) -> dict:
        return _android_verdict()

    monkeypatch.setattr(app_integrity_common, "APP_INTEGRITY_MODE", "enforce")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_DEV_TOKEN", None)
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_VERIFIER_URL", None)
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_ANDROID_PACKAGE_NAME", "com.example.app")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_ANDROID_CERT_SHA256_DIGESTS", "cert-digest")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_ANDROID_ALLOWED_DEVICE_VERDICTS", "MEETS_DEVICE_INTEGRITY")
    monkeypatch.setattr(app_integrity, "_decode_android_integrity_token", fake_decode_android_integrity_token)

    await app_integrity.verify_app_integrity_request(
        _request(_integrity_headers(platform="android", token="play-token")),
        action="orders:create",
    )


@pytest.mark.anyio
async def test_app_integrity_enforce_rejects_android_cert_mismatch(monkeypatch: pytest.MonkeyPatch):
    async def fake_decode_android_integrity_token(_token: str) -> dict:
        return _android_verdict()

    monkeypatch.setattr(app_integrity_common, "APP_INTEGRITY_MODE", "enforce")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_DEV_TOKEN", None)
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_VERIFIER_URL", None)
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_ANDROID_PACKAGE_NAME", "com.example.app")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_ANDROID_CERT_SHA256_DIGESTS", "other-cert-digest")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_ANDROID_ALLOWED_DEVICE_VERDICTS", "MEETS_DEVICE_INTEGRITY")
    monkeypatch.setattr(app_integrity, "_decode_android_integrity_token", fake_decode_android_integrity_token)

    with pytest.raises(HTTPException) as exc_info:
        await app_integrity.verify_app_integrity_request(
            _request(_integrity_headers(platform="android", token="play-token")),
            action="orders:create",
        )

    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_app_integrity_enforce_rejects_android_request_hash_mismatch(monkeypatch: pytest.MonkeyPatch):
    async def fake_decode_android_integrity_token(_token: str) -> dict:
        return _android_verdict(request_hash="other-request-hash")

    monkeypatch.setattr(app_integrity_common, "APP_INTEGRITY_MODE", "enforce")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_DEV_TOKEN", None)
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_VERIFIER_URL", None)
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_ANDROID_PACKAGE_NAME", "com.example.app")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_ANDROID_CERT_SHA256_DIGESTS", "cert-digest")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_ANDROID_ALLOWED_DEVICE_VERDICTS", "MEETS_DEVICE_INTEGRITY")
    monkeypatch.setattr(app_integrity, "_decode_android_integrity_token", fake_decode_android_integrity_token)

    with pytest.raises(HTTPException) as exc_info:
        await app_integrity.verify_app_integrity_request(
            _request(_integrity_headers(platform="android", token="play-token")),
            action="orders:create",
        )

    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_register_ios_app_attest_key_consumes_challenge_and_stores_key(monkeypatch: pytest.MonkeyPatch):
    challenge = SimpleNamespace(consumed_at=None)
    db = _FakeDb([challenge, None])

    def fake_verify_ios_attestation_object(**_kwargs):
        return IosAttestationVerification(
            public_key_pem="public-key-pem",
            receipt_b64="receipt",
            environment="production",
        )

    monkeypatch.setattr(app_integrity, "verify_ios_attestation_object", fake_verify_ios_attestation_object)

    key = await app_integrity.register_ios_app_attest_key(
        db,
        user_id=123,
        key_id="key-id",
        challenge="challenge",
        attestation_object="attestation",
    )

    assert challenge.consumed_at is not None
    assert db.commits == 2
    assert key in db.added
    assert key.user_id == 123
    assert key.key_id == "key-id"
    assert key.public_key_pem == "public-key-pem"
    assert key.receipt_b64 == "receipt"
    assert key.environment == "production"
    assert key.is_active is True


@pytest.mark.anyio
async def test_app_integrity_enforce_accepts_ios_assertion_and_updates_counter(monkeypatch: pytest.MonkeyPatch):
    challenge = SimpleNamespace(consumed_at=None)
    app_attest_key = SimpleNamespace(public_key_pem="public-key-pem", counter=7)
    db = _FakeDb([challenge, app_attest_key])

    def fake_verify_ios_assertion_signature(**kwargs):
        assert kwargs["public_key_pem"] == "public-key-pem"
        assert kwargs["challenge"] == "test-request-hash"
        assert kwargs["assertion_b64"] == "assertion"
        return 8

    monkeypatch.setattr(app_integrity_common, "APP_INTEGRITY_MODE", "enforce")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_DEV_TOKEN", None)
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_VERIFIER_URL", None)
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_ANDROID_PACKAGE_NAME", None)
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_IOS_TEAM_ID", "TEAMID1234")
    monkeypatch.setattr(app_integrity, "APP_INTEGRITY_IOS_BUNDLE_ID", "com.example.app")
    monkeypatch.setattr(app_integrity, "verify_ios_assertion_signature", fake_verify_ios_assertion_signature)

    await app_integrity.verify_app_integrity_request(
        _request(_integrity_headers(token="assertion", key_id="key-id")),
        action="orders:create",
        db=db,
        current_user=SimpleNamespace(id=123),
    )

    assert challenge.consumed_at is not None
    assert app_attest_key.counter == 8
    assert db.commits == 2


@pytest.mark.anyio
async def test_ios_assertion_rejects_stale_counter_after_consuming_challenge(monkeypatch: pytest.MonkeyPatch):
    challenge = SimpleNamespace(consumed_at=None)
    app_attest_key = SimpleNamespace(public_key_pem="public-key-pem", counter=8)
    db = _FakeDb([challenge, app_attest_key])

    monkeypatch.setattr(app_integrity, "verify_ios_assertion_signature", lambda **_kwargs: 8)

    verified, reason = await app_integrity._verify_ios_app_attest_assertion(
        db,
        user_id=123,
        key_id="key-id",
        assertion="assertion",
        challenge="challenge",
        action="orders:create",
    )

    assert verified is False
    assert reason == "stale iOS assertion counter"
    assert challenge.consumed_at is not None
    assert db.commits == 1
