from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.app.modules.auth.schemas.login import UserLoginPayload
from src.app.services.auth import service as auth
from src.app.services.security import hash_password


@pytest.fixture
def review_user():
    return SimpleNamespace(
        id=42, username="app-review", email="review@example.com",
        is_active=True, is_verified=True,
        app_password_reset_at=None,
        password_hash=hash_password("test-review-password-only"),
    )


@pytest.mark.parametrize("username,expected", [
    ("app-review", True),
    ("customer", False),
    ("admin", False),
    ("App-Review", False),
    ("app-review-extra", False),
    (None, False),
])
def test_review_exception_matches_only_the_reserved_login(username, expected):
    assert auth._is_app_review_identity(SimpleNamespace(username=username)) is expected
    assert auth._is_app_review_identity(None) is False


@pytest.mark.anyio
@pytest.mark.parametrize("login", ["app-review", "review@example.com"])
async def test_review_login_still_checks_password_and_returns_customer_tokens(monkeypatch, review_user, login):
    rate_limit = AsyncMock()
    tokens = AsyncMock(return_value={"access_token": "customer-token"})
    email_code = AsyncMock()
    website = AsyncMock(side_effect=AssertionError("Review identity must remain local"))
    _patched_value_49 = rate_limit
    for target in ('src.app.services.auth.service.email._apply_auth_rate_limit', 'src.app.services.auth.service.phone._apply_auth_rate_limit', 'src.app.services.auth.service.rate_limits._apply_auth_rate_limit', 'src.app.services.auth.service.sessions._apply_auth_rate_limit', 'src.app.services.auth.service.telegram._apply_auth_rate_limit',):
        monkeypatch.setattr(target, _patched_value_49)
    _patched_value_50 = tokens
    for target in ('src.app.services.auth.service.email._build_auth_tokens_response', 'src.app.services.auth.service.phone._build_auth_tokens_response', 'src.app.services.auth.service.sessions._build_auth_tokens_response', 'src.app.services.auth.service.telegram._build_auth_tokens_response',):
        monkeypatch.setattr(target, _patched_value_50)
    _patched_value_51 = email_code
    for target in ('src.app.services.auth.service.email._create_and_send_verification_code', 'src.app.services.auth.service.phone._create_and_send_verification_code', 'src.app.services.auth.service.verification._create_and_send_verification_code',):
        monkeypatch.setattr(target, _patched_value_51)
    _patched_value_52 = AsyncMock(return_value=review_user)
    for target in ('src.app.services.auth.service.email.get_user_by_email', 'src.app.services.auth.service.login.get_user_by_email', 'src.app.services.auth.service.phone.get_user_by_email', 'src.app.services.auth.service.website.get_user_by_email',):
        monkeypatch.setattr(target, _patched_value_52)
    _patched_value_53 = AsyncMock(return_value=review_user)
    for target in ('src.app.services.auth.service.login.get_user_by_username', 'src.app.services.auth.service.website.get_user_by_username',):
        monkeypatch.setattr(target, _patched_value_53)
    monkeypatch.setattr('src.app.services.auth.service.login.website_identity_configured', lambda: True)
    monkeypatch.setattr('src.app.services.auth.service.login.WebsiteIdentityClient', lambda: SimpleNamespace(authenticate=website))
    db = object()
    response = await auth.login_user(object(), UserLoginPayload(login=login, password="test-review-password-only"), db)
    assert response == {"access_token": "customer-token"}
    rate_limit.assert_awaited_once()
    tokens.assert_awaited_once_with(review_user, db)
    email_code.assert_not_awaited()
    website.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("active,verified,password", [
    (True, True, "wrong-password"),
    (False, True, "test-review-password-only"),
    (True, False, "test-review-password-only"),
])
async def test_review_rejects_invalid_credentials_without_site_fallback(
    monkeypatch, review_user, active, verified, password,
):
    review_user.is_active, review_user.is_verified = active, verified
    tokens, email_code, website = AsyncMock(), AsyncMock(), AsyncMock()
    _patched_value_77 = AsyncMock()
    for target in ('src.app.services.auth.service.email._apply_auth_rate_limit', 'src.app.services.auth.service.phone._apply_auth_rate_limit', 'src.app.services.auth.service.rate_limits._apply_auth_rate_limit', 'src.app.services.auth.service.sessions._apply_auth_rate_limit', 'src.app.services.auth.service.telegram._apply_auth_rate_limit',):
        monkeypatch.setattr(target, _patched_value_77)
    _patched_value_78 = tokens
    for target in ('src.app.services.auth.service.email._build_auth_tokens_response', 'src.app.services.auth.service.phone._build_auth_tokens_response', 'src.app.services.auth.service.sessions._build_auth_tokens_response', 'src.app.services.auth.service.telegram._build_auth_tokens_response',):
        monkeypatch.setattr(target, _patched_value_78)
    _patched_value_79 = email_code
    for target in ('src.app.services.auth.service.email._create_and_send_verification_code', 'src.app.services.auth.service.phone._create_and_send_verification_code', 'src.app.services.auth.service.verification._create_and_send_verification_code',):
        monkeypatch.setattr(target, _patched_value_79)
    _patched_value_80 = AsyncMock(return_value=review_user)
    for target in ('src.app.services.auth.service.login.get_user_by_username', 'src.app.services.auth.service.website.get_user_by_username',):
        monkeypatch.setattr(target, _patched_value_80)
    monkeypatch.setattr('src.app.services.auth.service.login.website_identity_configured', lambda: True)
    monkeypatch.setattr('src.app.services.auth.service.login.WebsiteIdentityClient', lambda: SimpleNamespace(authenticate=website))
    with pytest.raises(HTTPException) as exc:
        await auth.login_user(object(), UserLoginPayload(login="app-review", password=password), object())
    assert exc.value.status_code == 401
    tokens.assert_not_awaited()
    email_code.assert_not_awaited()
    website.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("username", ["customer", "admin", "App-Review"])
async def test_other_customers_still_require_otp(monkeypatch, review_user, username):
    review_user.username = username
    email = review_user.email
    tokens, email_code = AsyncMock(), AsyncMock()
    db = SimpleNamespace(commit=AsyncMock())
    _patched_value_98 = AsyncMock()
    for target in ('src.app.services.auth.service.email._apply_auth_rate_limit', 'src.app.services.auth.service.phone._apply_auth_rate_limit', 'src.app.services.auth.service.rate_limits._apply_auth_rate_limit', 'src.app.services.auth.service.sessions._apply_auth_rate_limit', 'src.app.services.auth.service.telegram._apply_auth_rate_limit',):
        monkeypatch.setattr(target, _patched_value_98)
    _patched_value_99 = AsyncMock(return_value=review_user)
    for target in ('src.app.services.auth.service.email._get_login_user', 'src.app.services.auth.service.login._get_login_user',):
        monkeypatch.setattr(target, _patched_value_99)
    _patched_value_100 = tokens
    for target in ('src.app.services.auth.service.email._build_auth_tokens_response', 'src.app.services.auth.service.phone._build_auth_tokens_response', 'src.app.services.auth.service.sessions._build_auth_tokens_response', 'src.app.services.auth.service.telegram._build_auth_tokens_response',):
        monkeypatch.setattr(target, _patched_value_100)
    _patched_value_101 = email_code
    for target in ('src.app.services.auth.service.email._create_and_send_verification_code', 'src.app.services.auth.service.phone._create_and_send_verification_code', 'src.app.services.auth.service.verification._create_and_send_verification_code',):
        monkeypatch.setattr(target, _patched_value_101)
    response = await auth.login_user(object(), UserLoginPayload(login=email, password="test-review-password-only"), db)
    assert response.verification_required is True
    email_code.assert_awaited_once_with(review_user, db)
    db.commit.assert_awaited_once()
    tokens.assert_not_awaited()


@pytest.mark.anyio
async def test_website_identity_cannot_overwrite_the_reserved_review_customer(monkeypatch, review_user):
    from src.app.services.auth.service import website
    monkeypatch.setattr(website, "get_user_by_email", AsyncMock(return_value=None))
    monkeypatch.setattr(website, "get_user_by_username", AsyncMock(return_value=review_user))
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one=lambda: review_user)))
    original_hash = review_user.password_hash
    with pytest.raises(HTTPException) as error:
        await website._sync_user_from_website_identity(
            identity={"user": {"login": "app-review", "email": "another@example.com"}},
            requested_login="another@example.com", requested_email="another@example.com",
            password="website-password", db=db, user=None,
        )
    assert error.value.status_code == 401
    assert review_user.password_hash == original_hash
    assert review_user.email == "review@example.com"
