import secrets
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import ufa_now
from src.database.models import ReferralProfile, ReferralPromoCode, ReferralRelationship, User
from .calculations import OWN_PROMO_PURCHASE_THRESHOLD
from .profile import MAX_REFERRAL_TREE_LEVEL, get_or_create_referral_profile, normalize_referral_code, referral_profile_total_purchases, refresh_profile_discount, website_seed_referral_percent


async def find_referral_promo_code(db: AsyncSession, code: str | None) -> ReferralPromoCode | None:
    code = normalize_referral_code(code)
    if code is None: return None
    return (await db.execute(select(ReferralPromoCode).where(func.lower(ReferralPromoCode.code) == code.lower()))).scalar_one_or_none()


async def active_relationship_for_user(db: AsyncSession, user_id: int) -> ReferralRelationship | None:
    stmt = select(ReferralRelationship).where(ReferralRelationship.referred_user_id == user_id, ReferralRelationship.is_active.is_(True)).order_by(ReferralRelationship.started_at.desc(), ReferralRelationship.id.desc()).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def relationship_depth_for_new_referral(db: AsyncSession, referrer_user_id: int) -> int:
    depth, current, visited = 2, referrer_user_id, set()

    while current is not None:
        if current in visited: return MAX_REFERRAL_TREE_LEVEL + 1
        visited.add(current)

        relationship = await active_relationship_for_user(db, current)
        if relationship is None or relationship.referrer_user_id is None: break

        depth += 1
        current = relationship.referrer_user_id

    return depth


async def ensure_referral_promo_code(db: AsyncSession, *, owner_user_id: int, code: str, source_system: str, issued_at=None) -> ReferralPromoCode:
    code = normalize_referral_code(code)
    if code is None: raise ValueError("Referral promo code is required")

    existing = await find_referral_promo_code(db, code)
    if existing: return existing

    promo = ReferralPromoCode(code=code, owner_user_id=owner_user_id, is_active=True, source_system=source_system, issued_at=issued_at or ufa_now())
    db.add(promo)
    await db.flush()
    return promo


async def ensure_own_promo_code(db: AsyncSession, profile: ReferralProfile, *, source_system: str = "app") -> ReferralPromoCode | None:
    if profile.own_promo_code: return await ensure_referral_promo_code(db, owner_user_id=profile.user_id, code=profile.own_promo_code, source_system=source_system, issued_at=profile.own_promo_issued_at)
    if referral_profile_total_purchases(profile) < OWN_PROMO_PURCHASE_THRESHOLD: return None

    for _ in range(20):
        code = normalize_referral_code(f"EP{profile.user_id}{secrets.token_hex(2)}")
        if code and await find_referral_promo_code(db, code) is None:
            profile.own_promo_code = code
            profile.own_promo_issued_at = ufa_now()
            return await ensure_referral_promo_code(db, owner_user_id=profile.user_id, code=code, source_system=source_system, issued_at=profile.own_promo_issued_at)

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not generate referral promo code")


async def check_referrer_code(db: AsyncSession, *, user: User, code: str) -> dict[str, Any]:
    code = normalize_referral_code(code)
    profile = await get_or_create_referral_profile(db, user=user)
    response = {"code": code, "is_valid": False, "status": "not_found", "reason": "Promo code was not found", "warning": None, "requires_confirmation": False, "referrer_user_id": None}

    if code is None:
        response.update(status="empty", reason="Promo code is required")
        return response

    own_code = normalize_referral_code(profile.own_promo_code)
    if own_code and own_code.casefold() == code.casefold():
        response.update(status="own_code", reason="Clients cannot use their own referral promo code")
        return response

    promo = await find_referral_promo_code(db, code)
    if promo is None: return response

    response["referrer_user_id"] = promo.owner_user_id
    if not promo.is_active:
        response.update(status="inactive", reason="Promo code is inactive")
        return response

    if promo.owner_user_id == user.id:
        response.update(status="own_code", reason="Clients cannot use their own referral promo code")
        return response

    depth = await relationship_depth_for_new_referral(db, promo.owner_user_id)
    if depth > MAX_REFERRAL_TREE_LEVEL:
        response.update(status="max_depth", reason="Referral tree is already at the maximum supported depth")
        return response

    current_code = normalize_referral_code(profile.referrer_promo_code)
    replacing_seed = current_code is None and website_seed_referral_percent(profile) > Decimal("0.00") and profile.referral_discount_base_total > Decimal("0.00")
    replacing = bool(current_code and current_code.casefold() != code.casefold()) or replacing_seed

    response.update(is_valid=True, status="available", reason=None, warning="Changing the referrer promo resets the active referral discount path to 3%" if replacing else None, requires_confirmation=replacing, depth=depth)
    return response


async def attach_referrer_code(db: AsyncSession, *, user: User, code: str, confirmed: bool = False) -> ReferralProfile:
    check = await check_referrer_code(db, user=user, code=code)
    if not check["is_valid"]: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=check["reason"] or "Invalid promo code")
    if check["requires_confirmation"] and not confirmed: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=check["warning"])

    promo = await find_referral_promo_code(db, check["code"])
    if promo is None: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Promo code was not found")

    profile = await get_or_create_referral_profile(db, user=user)
    current_code, now = normalize_referral_code(profile.referrer_promo_code), ufa_now()
    if current_code and current_code.casefold() == check["code"].casefold(): return profile

    active = list((await db.execute(select(ReferralRelationship).where(ReferralRelationship.referred_user_id == user.id, ReferralRelationship.is_active.is_(True)))).scalars())
    for item in active:
        item.is_active = False
        item.ended_at = now

    relationship = ReferralRelationship(referred_user_id=user.id, referrer_user_id=promo.owner_user_id, referral_promo_code_id=promo.id, referrer_promo_code=check["code"], depth=int(check.get("depth") or 2), source_system="app", is_active=True, started_at=now)
    db.add(relationship)
    await db.flush()

    for item in active: item.replaced_by_relationship_id = relationship.id

    profile.referrer_promo_code = check["code"]
    profile.referrer_user_id = promo.owner_user_id
    profile.referrer_attached_at = profile.referrer_attached_at or now
    profile.promo_changed_at = now if current_code else profile.promo_changed_at
    profile.referral_discount_base_total = Decimal("0.00")
    refresh_profile_discount(profile)

    await db.flush()
    return profile


async def detach_referrer_code(db: AsyncSession, *, user: User) -> ReferralProfile:
    profile = await get_or_create_referral_profile(db, user=user)
    if normalize_referral_code(profile.referrer_promo_code) is None: return profile

    now = ufa_now()
    active = list((await db.execute(select(ReferralRelationship).where(ReferralRelationship.referred_user_id == user.id, ReferralRelationship.is_active.is_(True)))).scalars())
    for item in active:
        item.is_active = False
        item.ended_at = now

    profile.referrer_promo_code = None
    profile.referrer_user_id = None
    profile.promo_changed_at = now
    profile.referral_discount_base_total = Decimal("0.00")
    refresh_profile_discount(profile)

    await db.flush()
    return profile