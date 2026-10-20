from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from src.app.services.security import hash_password
from src.database.crud.auth.user import create_user, get_user_by_email, get_user_by_username
from src.database.limits import PERSON_NAME_MAX_LENGTH, USERNAME_MAX_LENGTH
from src.database.models.auth.user import User
from src.database.schemas.auth.user import UserCreate
from src.normalize import normalize_email, optional_str
from .common import logger


async def _sync_user_from_website_identity(*, identity: dict, requested_login: str, requested_email: str | None, password: str, db: AsyncSession, user: User | None,) -> User:
    website_user = identity.get("user")
    if not isinstance(website_user, dict): raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Website identity response is invalid")
    website_login = optional_str(website_user.get("login"))
    website_email = normalize_email(website_user.get("email"))
    identity_matches = (bool(website_email and website_email == requested_email) if requested_email else bool(website_login and website_login.casefold() == requested_login.casefold()))
    if not website_login or not website_email or not identity_matches:
        logger.warning("Website identity returned a mismatched login")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Website identity response is invalid")

    if user is None: user = await get_user_by_email(db, website_email)
    if user is None: user = await get_user_by_username(db, website_login)

    website_name = optional_str(website_user.get("name")) or "Customer"
    website_surname = optional_str(website_user.get("last_name")) or "Customer"
    discounts = identity.get("discounts")
    referral_program = discounts.get("referral_program") if isinstance(discounts, dict) else None
    has_referrer_promo_snapshot = (isinstance(referral_program, dict) and "referrer_promo_code" in referral_program)
    website_referrer_promo = (optional_str(referral_program.get("referrer_promo_code")) if isinstance(referral_program, dict) else None)
    password_hash = hash_password(password)

    if user is None: user = await create_user(db, UserCreate(email=website_email, username=website_login[:USERNAME_MAX_LENGTH], password_hash=password_hash, name=website_name[:PERSON_NAME_MAX_LENGTH], surname=website_surname[:PERSON_NAME_MAX_LENGTH], phone_number=None, is_verified=True, promo_code=website_referrer_promo,), commit=False,)
    else:
        user.username = website_login[:USERNAME_MAX_LENGTH]
        user.password_hash = password_hash
        user.is_active = True
        user.is_verified = True
        if not optional_str(user.name): user.name = website_name[:PERSON_NAME_MAX_LENGTH]
        if not optional_str(user.surname): user.surname = website_surname[:PERSON_NAME_MAX_LENGTH]
        # Bitrix is the source of truth for the promo assigned by a referrer.
        # The user's own promo must never be used for their purchases.
        if has_referrer_promo_snapshot: user.promo_code = website_referrer_promo
        await db.flush()

    return user
