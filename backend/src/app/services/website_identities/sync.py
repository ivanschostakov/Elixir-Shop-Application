import secrets
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import ufa_now
from src.app.services.referrals import seed_referral_profile_from_website_payload
from src.app.services.security import hash_password
from src.database.crud import (
    create_user,
    create_website_identity,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    get_website_identity_by_id,
    get_website_identity_by_user_id,
    get_website_identity_by_website_user_id,
    update_user,
    update_website_identity,
)
from src.database.limits import EMAIL_MAX_LENGTH, USERNAME_MAX_LENGTH
from src.database.models import User, WebsiteIdentity
from src.database.schemas import UserCreate, UserUpdate, WebsiteIdentityCreate, WebsiteIdentityUpdate
from src.normalize import lower_optional_str, normalize_email, normalize_username, optional_str
from .payloads import build_website_identity_payload, extract_website_profile
from .relationships import sync_website_identity_relationships


async def build_unique_username(db: AsyncSession, preferred: str, *, fallback_seed: int) -> str:
    fallback = f"site_{fallback_seed}"
    base = normalize_username(preferred, fallback=fallback)
    existing = await get_user_by_username(db, base)
    if not existing: return base
    for index in range(2, 10000):
        suffix = f"_{index}"
        candidate = f"{base[: max(1, USERNAME_MAX_LENGTH - len(suffix))]}{suffix}"
        if not await get_user_by_username(db, candidate): return candidate

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not allocate a unique username")


async def build_unique_email(db: AsyncSession, preferred: str | None, *, fallback_seed: int) -> str:
    normalized = normalize_email(preferred)
    if normalized:
        existing = await get_user_by_email(db, normalized)
        if not existing: return normalized

    base_local = f"website_{fallback_seed}"
    domain = "identity.elixir.local"
    candidate = f"{base_local}@{domain}"[:EMAIL_MAX_LENGTH]
    if not await get_user_by_email(db, candidate): return candidate
    for index in range(2, 10000):
        local = f"{base_local}_{index}"
        candidate = f"{local}@{domain}"[:EMAIL_MAX_LENGTH]
        if not await get_user_by_email(db, candidate): return candidate

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not allocate a unique email")


async def sync_local_user_from_website_payload(db: AsyncSession, user: User, payload: dict[str, Any]) -> User:
    profile = extract_website_profile(payload)

    phone_number = optional_str(profile.get("personal_phone")) or optional_str(profile.get("personal_mobile"))
    next_email = normalize_email(profile.get("email"))
    if next_email and next_email != lower_optional_str(user.email):
        existing_by_email = await get_user_by_email(db, next_email)
        if existing_by_email is not None and existing_by_email.id != user.id:
            next_email = None

    user_update_data: dict[str, Any] = {
        "name": optional_str(profile.get("name")) or user.name,
        "surname": optional_str(profile.get("last_name")) or user.surname,
        "is_verified": True,
        "last_active_at": ufa_now(),
    }
    if next_email: user_update_data["email"] = next_email
    if phone_number: user_update_data["phone_number"] = phone_number

    return await update_user(db, user, UserUpdate(**user_update_data), commit=False)


async def create_local_user_from_website_payload(db: AsyncSession, payload: dict[str, Any]) -> User:
    profile = extract_website_profile(payload)
    website_user_id = int(profile["id"])
    email = await build_unique_email(db, optional_str(profile.get("email")), fallback_seed=website_user_id)
    username = await build_unique_username(db, optional_str(profile.get("login")) or email.split("@", 1)[0], fallback_seed=website_user_id)
    phone_number = optional_str(profile.get("personal_phone")) or optional_str(profile.get("personal_mobile"))

    user_create = UserCreate(
        username=username,
        email=email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        name=optional_str(profile.get("name")) or "Website",
        surname=optional_str(profile.get("last_name")) or "User",
        phone_number=phone_number,
        is_verified=True,
    )
    return await create_user(db, user_create, commit=False)


async def resolve_user_for_website_login(db: AsyncSession, payload: dict[str, Any]) -> User:
    profile = extract_website_profile(payload)
    website_user_id = int(profile["id"])

    existing_identity = await get_website_identity_by_website_user_id(db, website_user_id)
    if existing_identity is not None:
        user = await get_user_by_id(db, existing_identity.user_id)
        if user is not None: return await sync_local_user_from_website_payload(db, user, payload)

    email = normalize_email(profile.get("email"))
    if email:
        user = await get_user_by_email(db, email)
        if user is not None:
            existing_user_identity = await get_website_identity_by_user_id(db, user.id)
            if existing_user_identity is not None and existing_user_identity.website_user_id != website_user_id: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already linked to another website identity")
            return await sync_local_user_from_website_payload(db, user, payload)

    return await create_local_user_from_website_payload(db, payload)


async def _upsert_website_identity_for_user(db: AsyncSession, *, user: User, payload: dict[str, Any]) -> WebsiteIdentity:
    website_identity_data = build_website_identity_payload(user_id=user.id, payload=payload)
    website_user_id = int(website_identity_data["website_user_id"])

    existing_by_website_user = await get_website_identity_by_website_user_id(db, website_user_id)
    if existing_by_website_user is not None and existing_by_website_user.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Website identity is already linked to another user")

    existing_by_user = await get_website_identity_by_user_id(db, user.id)
    if existing_by_user is None:
        website_identity = await create_website_identity(db, WebsiteIdentityCreate(**website_identity_data), commit=False)
        return await sync_website_identity_relationships(db, website_identity=website_identity, payload=payload)

    if existing_by_user.website_user_id != website_user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already linked to another website identity")

    website_identity = await update_website_identity(db, existing_by_user, WebsiteIdentityUpdate(**website_identity_data), commit=False)
    return await sync_website_identity_relationships(db, website_identity=website_identity, payload=payload)


async def sync_website_identity_payload_for_user(db: AsyncSession, *, user: User, payload: dict[str, Any]) -> WebsiteIdentity:
    try:
        synced_user = await sync_local_user_from_website_payload(db, user, payload)
        website_identity = await _upsert_website_identity_for_user(db, user=synced_user, payload=payload)
        await seed_referral_profile_from_website_payload(db, user=synced_user, website_identity=website_identity, payload=payload)
        await db.commit()

    except Exception:
        await db.rollback()
        raise

    refreshed_identity = await get_website_identity_by_id(db, website_identity.id)
    assert refreshed_identity is not None
    return refreshed_identity


async def refresh_linked_website_identity(db: AsyncSession, *, website_identity: WebsiteIdentity, payload: dict[str, Any]) -> WebsiteIdentity:
    user = await get_user_by_id(db, website_identity.user_id)
    if user is None: raise RuntimeError(f"Linked user {website_identity.user_id} was not found")
    return await sync_website_identity_payload_for_user(db, user=user, payload=payload)
