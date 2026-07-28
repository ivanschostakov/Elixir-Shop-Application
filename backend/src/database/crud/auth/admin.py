from sqlalchemy.ext.asyncio import AsyncSession


async def is_admin_user(session: AsyncSession, user_id: int) -> bool:
    """Customer tokens never grant admin privileges.

    Admin authentication uses the isolated ``admin_identities`` and
    ``admin_sessions`` tables. Numeric IDs from the two identity stores may
    overlap and therefore must never be compared.
    """

    del session, user_id
    return False
