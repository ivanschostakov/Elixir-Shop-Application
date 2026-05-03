from decimal import Decimal
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.normalize import lower_optional_str, optional_str
from src.database.models import WebsiteBonusAccount, WebsiteCoupon, WebsiteDiscountEntitlement, WebsiteReferralProfile


def _coupon_key_from_row(row: dict[str, Any]) -> tuple[str, str]:
    external_id = row.get("website_coupon_external_id")
    if external_id is not None: return "external_id", str(external_id)
    coupon_code = lower_optional_str(row.get("coupon_code"))
    return "coupon_code", coupon_code or ""


def _coupon_key_from_model(coupon: WebsiteCoupon) -> tuple[str, str]:
    if coupon.website_coupon_external_id is not None: return "external_id", str(coupon.website_coupon_external_id)
    return "coupon_code", lower_optional_str(coupon.coupon_code) or ""


def _entitlement_key_from_row(row: dict[str, Any]) -> tuple[str, str, str]:
    website_source_id = optional_str(row.get("website_source_id"))
    source_name = lower_optional_str(row.get("source_name")) or ""
    return row["source_kind"], website_source_id or "", source_name


def _entitlement_key_from_model(entitlement: WebsiteDiscountEntitlement) -> tuple[str, str, str]:
    source_name = lower_optional_str(entitlement.source_name) or ""
    return entitlement.source_kind, entitlement.website_source_id or "", source_name


async def upsert_website_referral_profile(session: AsyncSession, *, website_identity_id: int, data: dict[str, Any] | None) -> None:
    existing = (await session.execute(select(WebsiteReferralProfile).where(WebsiteReferralProfile.website_identity_id == website_identity_id))).scalar_one_or_none()
    if data is None:
        if existing is not None: await session.delete(existing)
        return

    if existing is None:
        session.add(WebsiteReferralProfile(**data))
        return

    for field, value in data.items(): setattr(existing, field, value)


async def upsert_website_bonus_account(session: AsyncSession, *, website_identity_id: int, data: dict[str, Any] | None, last_synced_at) -> None:
    existing = (await session.execute(select(WebsiteBonusAccount).where(WebsiteBonusAccount.website_identity_id == website_identity_id))).scalar_one_or_none()
    if data is None:
        if existing is None: return
        existing.is_active = False
        existing.balance = Decimal("0.00")
        existing.last_synced_at = last_synced_at
        return

    if existing is None:
        session.add(WebsiteBonusAccount(**data))
        return

    for field, value in data.items(): setattr(existing, field, value)


async def sync_website_discount_entitlements(session: AsyncSession, *, website_identity_id: int, rows: list[dict[str, Any]], last_synced_at) -> None:
    existing_rows = list((await session.execute(select(WebsiteDiscountEntitlement).where(WebsiteDiscountEntitlement.website_identity_id == website_identity_id))).scalars())
    existing_by_key: dict[tuple[str, str, str], WebsiteDiscountEntitlement] = {}
    for existing in existing_rows: existing_by_key.setdefault(_entitlement_key_from_model(existing), existing)

    matched_ids: set[int] = set()
    for row in rows:
        key = _entitlement_key_from_row(row)
        existing = existing_by_key.get(key)
        if existing is None:
            session.add(WebsiteDiscountEntitlement(**row))
            continue

        matched_ids.add(existing.id)
        for field, value in row.items(): setattr(existing, field, value)

    for existing in existing_rows:
        if existing.id in matched_ids: continue
        existing.is_active = False
        existing.last_synced_at = last_synced_at


async def sync_website_coupon_snapshots(session: AsyncSession, *, website_identity_id: int, rows: list[dict[str, Any]], last_synced_at) -> None:
    existing_rows = list((await session.execute(select(WebsiteCoupon).where(WebsiteCoupon.website_identity_id == website_identity_id))).scalars())
    existing_by_key: dict[tuple[str, str], WebsiteCoupon] = {}
    for existing in existing_rows: existing_by_key.setdefault(_coupon_key_from_model(existing), existing)

    matched_ids: set[int] = set()
    for row in rows:
        key = _coupon_key_from_row(row)
        existing = existing_by_key.get(key)
        if existing is None:
            session.add(WebsiteCoupon(**row))
            continue

        matched_ids.add(existing.id)
        for field, value in row.items(): setattr(existing, field, value)

    for existing in existing_rows:
        if existing.id in matched_ids: continue
        existing.is_active = False
        existing.last_synced_at = last_synced_at
