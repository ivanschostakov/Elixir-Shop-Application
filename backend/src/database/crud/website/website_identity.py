from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import WebsiteIdentity
from src.database.schemas import WebsiteIdentityCreate, WebsiteIdentityUpdate


def _website_identity_select(): return select(WebsiteIdentity).options(selectinload(WebsiteIdentity.referral_profile), selectinload(WebsiteIdentity.bonus_account_snapshot), selectinload(WebsiteIdentity.discount_entitlements), selectinload(WebsiteIdentity.coupon_snapshots)).execution_options(populate_existing=True)


async def create_website_identity(session: AsyncSession, data: WebsiteIdentityCreate, *, commit: bool = True) -> WebsiteIdentity:
    website_identity = WebsiteIdentity(**data.model_dump())
    session.add(website_identity)
    if commit:
        await session.commit()
        return await get_website_identity_by_id(session, website_identity.id)

    await session.flush()
    await session.refresh(website_identity)
    return website_identity


async def get_website_identity_by_id(session: AsyncSession, website_identity_id: int) -> WebsiteIdentity | None: return (await session.execute(_website_identity_select().where(WebsiteIdentity.id == website_identity_id))).scalar_one_or_none()
async def get_website_identity_by_user_id(session: AsyncSession, user_id: int) -> WebsiteIdentity | None: return (await session.execute(_website_identity_select().where(WebsiteIdentity.user_id == user_id))).scalar_one_or_none()
async def get_website_identity_by_website_user_id(session: AsyncSession, website_user_id: int) -> WebsiteIdentity | None: return (await session.execute(_website_identity_select().where(WebsiteIdentity.website_user_id == website_user_id))).scalar_one_or_none()


async def update_website_identity(session: AsyncSession, website_identity: WebsiteIdentity, data: WebsiteIdentityUpdate, *, commit: bool = True) -> WebsiteIdentity:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(website_identity, field, value)
    if commit:
        await session.commit()
        return await get_website_identity_by_id(session, website_identity.id)

    await session.flush()
    await session.refresh(website_identity)
    return website_identity
