from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.database.crud import (
    sync_website_coupon_snapshots,
    sync_website_discount_entitlements,
    upsert_website_bonus_account,
    upsert_website_referral_profile,
)
from src.database.models import WebsiteIdentity

from .payloads import (
    build_bonus_account_payload,
    build_coupon_payloads,
    build_discount_entitlement_payloads,
    build_referral_profile_payload,
)

async def sync_website_identity_relationships(
    db: AsyncSession, *, website_identity: WebsiteIdentity, payload: dict[str, Any]
) -> WebsiteIdentity:
    last_synced_at = website_identity.last_synced_at or ufa_now()
    referral_profile_data = build_referral_profile_payload(
        website_identity_id=website_identity.id, payload=payload, last_synced_at=last_synced_at
    )
    bonus_account_data = build_bonus_account_payload(
        website_identity_id=website_identity.id, payload=payload, last_synced_at=last_synced_at
    )
    discount_entitlement_rows = build_discount_entitlement_payloads(
        website_identity_id=website_identity.id, payload=payload, last_synced_at=last_synced_at
    )
    coupon_snapshot_rows = build_coupon_payloads(
        website_identity_id=website_identity.id, payload=payload, last_synced_at=last_synced_at
    )

    await upsert_website_referral_profile(
        db, website_identity_id=website_identity.id, data=referral_profile_data
    )
    await upsert_website_bonus_account(
        db, website_identity_id=website_identity.id, data=bonus_account_data, last_synced_at=last_synced_at
    )
    await sync_website_discount_entitlements(
        db, website_identity_id=website_identity.id, rows=discount_entitlement_rows, last_synced_at=last_synced_at
    )
    await sync_website_coupon_snapshots(
        db, website_identity_id=website_identity.id, rows=coupon_snapshot_rows, last_synced_at=last_synced_at
    )
    return website_identity
