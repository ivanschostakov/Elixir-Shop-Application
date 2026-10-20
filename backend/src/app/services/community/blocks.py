from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from config import TELEGRAM_COMMUNITY_CHAT_ID
from src.database.schemas.community import CommunityAuthorRead
from src.database.models import CommunityAuthor, CommunityAuthorBlock, CommunityMessage, CommunityTopic, User


def _blocked_author_query(user_id: int):
    direct = select(CommunityAuthorBlock.author_id).where(CommunityAuthorBlock.user_id == user_id)
    # The same linked person can write through the app or Telegram.
    people = select(CommunityAuthor.app_user_id).where(CommunityAuthor.id.in_(direct), CommunityAuthor.app_user_id.is_not(None))
    return select(CommunityAuthor.id).where(or_(CommunityAuthor.id.in_(direct), CommunityAuthor.app_user_id.in_(people)))


async def blocked_community_author_ids(db: AsyncSession, user_id: int) -> set[int]:
    return set((await db.execute(_blocked_author_query(user_id))).scalars().all())


def visible_community_message(user_id: int):
    return or_(CommunityMessage.author_id.is_(None), CommunityMessage.author_id.not_in(_blocked_author_query(user_id)))


async def list_blocked_community_authors(db: AsyncSession, *, user: User) -> list[CommunityAuthorRead]:
    rows = (await db.execute(select(CommunityAuthor).join(CommunityAuthorBlock, CommunityAuthorBlock.author_id == CommunityAuthor.id).where(CommunityAuthorBlock.user_id == user.id).order_by(CommunityAuthor.full_name, CommunityAuthor.id))).scalars().all()
    return [CommunityAuthorRead(id=row.id, full_name=row.full_name) for row in rows]


async def block_community_author(db: AsyncSession, *, user: User, author_id: int) -> None:
    # Serialise duplicate requests from the same account without a unique-key race.
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    author = await db.get(CommunityAuthor, author_id)
    if author is None: raise HTTPException(404, "Community author not found")
    if author.app_user_id == user.id or (author.kind == "user" and author.telegram_peer_id == user.telegram_user_id): raise HTTPException(422, "You cannot block yourself")
    visible_author = (await db.execute(select(CommunityMessage.id).join(CommunityTopic).where(CommunityMessage.author_id == author_id, CommunityTopic.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTopic.is_hidden.is_(False), CommunityTopic.is_deleted.is_(False)).limit(1))).scalar_one_or_none()
    if visible_author is None: raise HTTPException(404, "Community author not found")
    exists = (await db.execute(select(CommunityAuthorBlock.id).where(CommunityAuthorBlock.user_id == user.id, CommunityAuthorBlock.author_id == author_id))).scalar_one_or_none()
    if exists is None: db.add(CommunityAuthorBlock(user_id=user.id, author_id=author_id))
    await db.commit()


async def unblock_community_author(db: AsyncSession, *, user: User, author_id: int) -> None:
    author = await db.get(CommunityAuthor, author_id)
    author_ids = select(CommunityAuthor.id).where(or_(CommunityAuthor.id == author_id, CommunityAuthor.app_user_id == author.app_user_id)) if author and author.app_user_id else [author_id]
    await db.execute(delete(CommunityAuthorBlock).where(CommunityAuthorBlock.user_id == user.id, CommunityAuthorBlock.author_id.in_(author_ids)))
    await db.commit()
