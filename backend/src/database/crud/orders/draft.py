from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import OrderDraft
from src.database.schemas import OrderDraftCreate, OrderDraftUpdate


def _order_draft_load_options():
    return (
        selectinload(OrderDraft.delivery_address),
        selectinload(OrderDraft.recipient),
        selectinload(OrderDraft.items),
    )


async def create_order_draft(session: AsyncSession, data: OrderDraftCreate, *, commit: bool = True) -> OrderDraft:
    draft = OrderDraft(**data.model_dump())
    session.add(draft)
    await session.flush()

    if commit:
        await session.commit()
        await session.refresh(draft)

    return draft


async def delete_order_draft(session: AsyncSession, draft: OrderDraft, *, commit: bool = True) -> None:
    await session.delete(draft)

    if commit:
        await session.commit()


async def update_order_draft(session: AsyncSession, draft: OrderDraft, data: OrderDraftUpdate, *, commit: bool = True) -> OrderDraft:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(draft, field, value)

    await session.flush()

    if commit:
        await session.commit()

    await session.refresh(draft)
    return draft


async def get_order_draft_by_id(session: AsyncSession, draft_id: int, *, user_id: int | None = None) -> OrderDraft | None:
    stmt = (
        select(OrderDraft)
        .options(*_order_draft_load_options())
        .where(OrderDraft.id == draft_id)
        .execution_options(populate_existing=True)
    )
    if user_id is not None:
        stmt = stmt.where(OrderDraft.user_id == user_id)

    return (await session.execute(stmt)).scalar_one_or_none()


async def get_latest_order_draft_for_user(session: AsyncSession, user_id: int) -> OrderDraft | None:
    stmt = (
        select(OrderDraft)
        .options(*_order_draft_load_options())
        .where(OrderDraft.user_id == user_id)
        .order_by(OrderDraft.created_at.desc(), OrderDraft.id.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_latest_named_order_draft_for_user(session: AsyncSession, user_id: int) -> OrderDraft | None:
    stmt = (
        select(OrderDraft)
        .options(*_order_draft_load_options())
        .where(OrderDraft.user_id == user_id, OrderDraft.draft_name.is_not(None))
        .order_by(OrderDraft.created_at.desc(), OrderDraft.id.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_order_drafts_for_user(session: AsyncSession, user_id: int, *, limit: int | None = 10, offset: int = 0, created_from: datetime | None = None, created_to: datetime | None = None, named_only: bool = False) -> list[OrderDraft]:
    stmt = (
        select(OrderDraft)
        .options(*_order_draft_load_options())
        .where(OrderDraft.user_id == user_id)
        .order_by(OrderDraft.created_at.desc(), OrderDraft.id.desc())
        .offset(offset)
        .execution_options(populate_existing=True)
    )

    if created_from is not None:
        stmt = stmt.where(OrderDraft.created_at >= created_from)

    if created_to is not None:
        stmt = stmt.where(OrderDraft.created_at <= created_to)

    if named_only:
        stmt = stmt.where(OrderDraft.draft_name.is_not(None))

    if limit is not None:
        stmt = stmt.limit(limit)

    return list((await session.execute(stmt)).scalars().all())
