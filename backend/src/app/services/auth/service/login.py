from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from config import AUTH_APP_REVIEW_EMAIL, AUTH_APP_REVIEW_USER_ID, AUTH_LOGIN_WEBSITE_FIRST_ENABLED
from src.app.modules.auth.schemas.login import UserLoginPayload
from src.app.services.security import verify_password
from src.database.crud.auth.user import get_user_by_email, get_user_by_username
from src.database.models.auth.user import User
from src.integrations.website_identity import WebsiteIdentityClient, WebsiteIdentityError, website_identity_configured
from src.normalize import normalize_email
from .common import logger
from .website import _sync_user_from_website_identity


def _is_app_review_identity(user: User | None) -> bool:
    return bool(user is not None and AUTH_APP_REVIEW_USER_ID > 0 and user.id == AUTH_APP_REVIEW_USER_ID and normalize_email(AUTH_APP_REVIEW_EMAIL) and normalize_email(user.email) == normalize_email(AUTH_APP_REVIEW_EMAIL))


async def _get_login_user(payload: UserLoginPayload, db: AsyncSession) -> User:
    requested_login = str(payload.login).strip()
    requested_email = normalize_email(requested_login)
    user = (await get_user_by_email(db, requested_email) if requested_email else await get_user_by_username(db, requested_login))
    local_authenticated = bool(user is not None and user.is_active and verify_password(payload.password, user.password_hash))

    # The dedicated review customer authenticates locally, never against a
    # website identity with the same email. Password and account state still
    # apply; this exception grants no administrative or device-integrity rights.
    if _is_app_review_identity(user):
        if local_authenticated and user.is_verified: return user
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    website_login_enabled = (AUTH_LOGIN_WEBSITE_FIRST_ENABLED and website_identity_configured())
    if not website_login_enabled:
        if local_authenticated:
            assert user is not None
            return user
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    try: identity = await WebsiteIdentityClient().authenticate(login=requested_login, password=payload.password,)
    except WebsiteIdentityError as error:
        if local_authenticated:
            assert user is not None
            if error.status_code not in (401, 404):
                logger.warning(
                    "Website identity promo refresh is temporarily unavailable: %s",
                    error.code,
                )
            return user
        if error.status_code in (401, 404): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from error
        logger.warning("Website identity authentication is temporarily unavailable: %s", error.code)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Website login is temporarily unavailable",) from error

    try: return await _sync_user_from_website_identity(identity=identity, requested_login=requested_login, requested_email=requested_email, password=payload.password, db=db, user=user,)
    except HTTPException:
        if local_authenticated:
            assert user is not None
            logger.warning(
                "Website identity returned invalid data during promo refresh; using the local account",
            )
            return user
        raise
