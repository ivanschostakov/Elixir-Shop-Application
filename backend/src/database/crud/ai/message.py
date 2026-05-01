from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import AIMessage, AIMessageUsage
from src.database.schemas import AIMessageCreate, AIMessageUpdate, AIMessageUsageCreate
from src.integrations.ai.enums import BotModel, MessageSender


def _ai_message_select():
    return (
        select(AIMessage)
        .options(selectinload(AIMessage.attachments), selectinload(AIMessage.usage))
        .execution_options(populate_existing=True)
    )


async def create_ai_message(session: AsyncSession, data: AIMessageCreate, *, commit: bool = True) -> AIMessage:
    message = AIMessage(**data.model_dump())
    session.add(message)
    await session.flush()

    if commit:
        await session.commit()
        return await get_ai_message_by_id(session, message.id)

    await session.refresh(message)
    return message


async def get_ai_message_by_id(session: AsyncSession, message_id: int, user_id: int | None = None, chat_id: int | None = None) -> AIMessage | None:
    stmt = _ai_message_select().where(AIMessage.id == message_id)
    if user_id is not None: stmt = stmt.where(AIMessage.user_id == user_id)
    if chat_id is not None: stmt = stmt.where(AIMessage.chat_id == chat_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_ai_messages(session: AsyncSession, user_id: int | None = None, chat_id: int | None = None, sender: MessageSender | None = None, bot_model: BotModel | None = None, offset: int = 0, limit: int = 100, newest_first: bool = False) -> list[AIMessage]:
    order_clause = AIMessage.id.desc() if newest_first else AIMessage.id.asc()
    stmt = _ai_message_select().order_by(order_clause).offset(offset).limit(limit)
    if user_id is not None: stmt = stmt.where(AIMessage.user_id == user_id)
    if chat_id is not None: stmt = stmt.where(AIMessage.chat_id == chat_id)
    if sender is not None: stmt = stmt.where(AIMessage.sender == sender)
    if bot_model is not None: stmt = stmt.join(AIMessageUsage).where(AIMessageUsage.bot_model == bot_model)
    return list((await session.execute(stmt)).scalars().all())


async def update_ai_message(session: AsyncSession, message: AIMessage, data: AIMessageUpdate, *, commit: bool = True) -> AIMessage:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(message, field, value)
    await session.flush()

    if commit:
        await session.commit()
        return await get_ai_message_by_id(session, message.id)

    await session.refresh(message)
    return message


async def delete_ai_message(session: AsyncSession, message: AIMessage, *, commit: bool = True) -> None:
    await session.delete(message)
    await session.flush()

    if commit: await session.commit()


async def create_ai_message_usage(
    session: AsyncSession,
    data: AIMessageUsageCreate,
    *,
    commit: bool = True,
) -> AIMessageUsage:
    usage = AIMessageUsage(**data.model_dump())
    session.add(usage)
    await session.flush()

    if commit:
        await session.commit()
        reloaded_usage = await get_ai_message_usage_by_message_id(session, usage.message_id)
        if reloaded_usage is None:
            raise RuntimeError("Failed to reload AI message usage")
        return reloaded_usage

    await session.refresh(usage)
    return usage


async def get_ai_message_usage_by_message_id(session: AsyncSession, message_id: int) -> AIMessageUsage | None:
    return (
        await session.execute(select(AIMessageUsage).where(AIMessageUsage.message_id == message_id))
    ).scalar_one_or_none()
