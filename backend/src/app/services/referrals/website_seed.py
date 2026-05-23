from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.app.services.website_identities.payloads import build_bonus_account_payload, build_referral_profile_payload
from src.database.models import User, WebsiteIdentity
from src.normalize import optional_str

from .calculations import quantize_money, quantize_percent
from .ledger import create_ledger_entry_if_missing
from .profile import get_or_create_referral_profile, normalize_referral_code, refresh_profile_discount, sync_website_referral_discount_base, website_discount_base_from_referral_data
from .promo import ensure_own_promo_code, ensure_referral_promo_code, find_referral_promo_code


async def seed_referral_profile_from_website_payload(db: AsyncSession, *, user: User, website_identity: WebsiteIdentity, payload: dict[str, Any]):
    now = website_identity.last_synced_at or ufa_now()
    referral_data = build_referral_profile_payload(website_identity_id=website_identity.id, payload=payload, last_synced_at=now)
    bonus_data = build_bonus_account_payload(website_identity_id=website_identity.id, payload=payload, last_synced_at=now)

    website_base = website_discount_base_from_referral_data(referral_data)
    website_percent = quantize_percent((referral_data or {}).get("referral_percent"))
    website_participates = bool(normalize_referral_code((referral_data or {}).get("referrer_promo_code")) or website_percent > Decimal("0.00"))

    profile = await get_or_create_referral_profile(db, user=user)
    is_first_seed = profile.website_seeded_at is None
    old_website_base = quantize_money(profile.website_seed_purchase_balance)

    if profile.website_identity_id is None: profile.website_identity_id = website_identity.id

    profile.website_seed_payload = jsonable_encoder({
        "website_identity_id": website_identity.id,
        "referral_profile": referral_data or {},
        "referral_app_baseline": {
            "participates": website_participates,
            "discount_base_total": website_base,
            "discount_percent": website_percent,
        },
        "bonus_account": bonus_data or {},
        "synced_at": now.isoformat(),
    })

    if referral_data is not None:
        profile.website_seed_purchase_balance = website_base
        profile.current_month_purchase_total = quantize_money(referral_data.get("monthly_paid_orders_amount"))
        if is_first_seed: profile.website_seeded_at = now

        own_code = normalize_referral_code(referral_data.get("own_promo_code"))
        if own_code and not profile.own_promo_code:
            profile.own_promo_code = own_code
            profile.own_promo_issued_at = now
            await ensure_referral_promo_code(db, owner_user_id=user.id, code=own_code, source_system="website_seed", issued_at=now)

        referrer_code = normalize_referral_code(referral_data.get("referrer_promo_code"))
        if referrer_code and not profile.referrer_promo_code:
            promo = await find_referral_promo_code(db, referrer_code)
            profile.referrer_promo_code = referrer_code
            profile.referrer_user_id = promo.owner_user_id if promo is not None and promo.owner_user_id != user.id else None
            profile.referrer_attached_at = now

        sync_website_referral_discount_base(
            profile,
            old_website_base=old_website_base,
            new_website_base=website_base,
            is_first_website_seed=is_first_seed,
            website_participates=website_participates,
        )

    await ensure_own_promo_code(db, profile, source_system="website_seed")
    refresh_profile_discount(profile)

    if bonus_data is not None:
        balance = quantize_money(bonus_data.get("balance"))
        if balance > Decimal("0.00"):
            await create_ledger_entry_if_missing(
                db,
                idempotency_key=f"website_bonus_seed:user:{user.id}",
                user_id=user.id,
                website_identity_id=website_identity.id,
                amount=balance,
                currency=optional_str(bonus_data.get("currency")) or "RUB",
                entry_type="website_bonus_seed",
                direction="credit",
                source_system="website_seed",
                source_code=str(website_identity.website_user_id),
                note="Initial deposit seed from linked website bonus balance",
                effective_at=now,
            )

    await db.flush()
    return profile