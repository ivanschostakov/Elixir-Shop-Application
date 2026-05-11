from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Banner
from src.database.schemas import BannerCreate, BannerUpdate


async def create_banner(session: AsyncSession, data: BannerCreate) -> Banner:
    banner = Banner(**data.model_dump())
    session.add(banner)
    await session.commit()
    await session.refresh(banner)
    return banner


async def get_banner_by_id(session: AsyncSession, banner_id: int, *, include_archived: bool = False) -> Banner | None:
    stmt = select(Banner).where(Banner.id == banner_id)
    if not include_archived:
        stmt = stmt.where(Banner.archived.is_(False))
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_banners(
    session: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 100,
    sort: str | None = None,
    include_archived: bool = False,
) -> list[Banner]:
    stmt = select(Banner)
    if not include_archived:
        stmt = stmt.where(Banner.archived.is_(False))

    sort_map = {
        "newest": (Banner.created_at.desc(), Banner.id.desc()),
        "priority_desc": (Banner.priority.desc(), Banner.id.desc()),
        "priority_asc": (Banner.priority.asc(), Banner.id.asc()),
    }
    if sort in sort_map:
        stmt = stmt.order_by(*sort_map[sort])
    else:
        stmt = stmt.order_by(Banner.priority.desc(), Banner.id.desc())

    stmt = stmt.offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_banner_by_image_path(session: AsyncSession, image_path: str) -> Banner | None:
    stmt = select(Banner).where(func.lower(Banner.image_path) == image_path.lower())
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_banner(session: AsyncSession, banner: Banner, data: BannerUpdate) -> Banner:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(banner, field, value)
    await session.commit()
    await session.refresh(banner)
    return banner


async def delete_banner(session: AsyncSession, banner: Banner) -> None:
    await session.delete(banner)
    await session.commit()
