from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.auth.admin import Admin


async def is_admin_user(session: AsyncSession, user_id: int) -> bool:
    stmt = select(exists().where(Admin.user_id == user_id, Admin.is_active.is_(True)))
    return bool((await session.execute(stmt)).scalar())
