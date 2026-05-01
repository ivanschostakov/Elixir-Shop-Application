from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import AIChat, AIMessage
from src.database.schemas import AIChatCreate, AIChatUpdate


def _ai_chat_select():
    return (
        select(AIChat)
        .options(
            selectinload(AIChat.messages).selectinload(AIMessage.attachments),
            selectinload(AIChat.messages).selectinload(AIMessage.usage),
        )
        .execution_options(populate_existing=True)
    )

async def create_ai_chat(session: AsyncSession, data: AIChatCreate, *, commit: bool = True) -> AIChat:
    chat = AIChat(**data.model_dump())
    session.add(chat)
    await session.flush()

    if commit:
        await session.commit()
        return await get_ai_chat_by_id(session, chat.id)

    await session.refresh(chat)
    return chat


async def get_ai_chat_by_id(session: AsyncSession, chat_id: int, *, user_id: int | None = None) -> AIChat | None:
    stmt = _ai_chat_select().where(AIChat.id == chat_id)
    if user_id is not None: stmt = stmt.where(AIChat.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_ai_chat_by_user_id(session: AsyncSession, user_id: int) -> AIChat | None: return (await session.execute(_ai_chat_select().where(AIChat.user_id == user_id))).scalar_one_or_none()
async def get_ai_chat_by_conversation_id(session: AsyncSession, conversation_id: str) -> AIChat | None: return (await session.execute(_ai_chat_select().where(AIChat.conversation_id == conversation_id))).scalar_one_or_none()


async def get_ai_chats(session: AsyncSession, *, user_id: int | None = None, offset: int = 0, limit: int = 100) -> list[AIChat]:
    stmt = _ai_chat_select().order_by(AIChat.id.desc()).offset(offset).limit(limit)
    if user_id is not None: stmt = stmt.where(AIChat.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def update_ai_chat(session: AsyncSession, chat: AIChat, data: AIChatUpdate, *, commit: bool = True) -> AIChat:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(chat, field, value)
    await session.flush()

    if commit:
        await session.commit()
        return await get_ai_chat_by_id(session, chat.id)

    await session.refresh(chat)
    return chat


async def delete_ai_chat(session: AsyncSession, chat: AIChat, *, commit: bool = True) -> None:
    await session.delete(chat)
    await session.flush()

    if commit: await session.commit()
