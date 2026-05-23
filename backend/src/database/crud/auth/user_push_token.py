from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import UserPushToken
from src.database.schemas import UserPushTokenUpsert


async def get_user_push_token_by_expo_token(session: AsyncSession, expo_push_token: str) -> UserPushToken | None:
    stmt = select(UserPushToken).where(UserPushToken.expo_push_token == expo_push_token)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_user_push_tokens(session: AsyncSession, *, user_id: int) -> list[UserPushToken]:
    stmt = (
        select(UserPushToken)
        .where(UserPushToken.user_id == user_id)
        .order_by(UserPushToken.updated_at.desc(), UserPushToken.id.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def upsert_user_push_token(session: AsyncSession, *, user_id: int, data: UserPushTokenUpsert, commit: bool = True) -> UserPushToken:
    push_token = await get_user_push_token_by_expo_token(session, data.expo_push_token)
    if push_token is None:
        push_token = UserPushToken(
            user_id=user_id,
            expo_push_token=data.expo_push_token,
            platform=data.platform,
            current_path=data.current_path,
        )
        session.add(push_token)
    else:
        push_token.user_id = user_id
        push_token.platform = data.platform
        push_token.current_path = data.current_path

    await session.flush()

    if commit:
        await session.commit()

    await session.refresh(push_token)
    return push_token


async def delete_user_push_token(session: AsyncSession, push_token: UserPushToken, *, commit: bool = True) -> None:
    await session.delete(push_token)
    await session.flush()

    if commit:
        await session.commit()
