from datetime import datetime

from sqlalchemy import String, and_, cast, func, literal, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import IntegrationRun, Order
from src.database.models.orders.history import (
    OrderHistoryBucket,
    OrderStatusCode,
    build_history_bucket_clause,
    build_status_code_clause,
)
from src.database.schemas import OrderCreate, OrderUpdate


def _order_load_options():
    return (
        selectinload(Order.delivery_address),
        selectinload(Order.recipient),
        selectinload(Order.items),
        selectinload(Order.user),
    )


async def create_order(session: AsyncSession, data: OrderCreate, *, commit: bool = True) -> Order:
    order = Order(**data.model_dump())
    session.add(order)
    await session.flush()

    if commit:
        await session.commit()
        await session.refresh(order)

    return order


async def update_order(session: AsyncSession, order: Order, data: OrderUpdate, *, commit: bool = True) -> Order:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(order, field, value)

    await session.flush()

    if commit:
        await session.commit()

    await session.refresh(order)
    return order


async def get_order_by_id(session: AsyncSession, order_id: int, *, user_id: int | None = None) -> Order | None:
    stmt = (
        select(Order)
        .options(*_order_load_options())
        .where(Order.id == order_id)
        .execution_options(populate_existing=True)
    )
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_order_by_code(session: AsyncSession, order_code: str, *, user_id: int | None = None) -> Order | None:
    stmt = (
        select(Order)
        .options(*_order_load_options())
        .where(Order.order_code == order_code)
        .execution_options(populate_existing=True)
    )
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_order_by_draft_id(session: AsyncSession, draft_id: int, *, user_id: int | None = None) -> Order | None:
    stmt = (
        select(Order)
        .options(*_order_load_options())
        .where(Order.draft_id == draft_id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_order_by_invoice_id(session: AsyncSession, invoice_id: str) -> Order | None:
    stmt = (
        select(Order)
        .options(*_order_load_options())
        .where(Order.payment_invoice_id == invoice_id)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_order_by_amocrm_lead_id(session: AsyncSession, lead_id: int) -> Order | None:
    stmt = (
        select(Order)
        .options(*_order_load_options())
        .where(Order.amocrm_lead_id == lead_id)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_orders_for_user(session: AsyncSession, user_id: int, *, history_bucket: OrderHistoryBucket | None = None, status_code: OrderStatusCode | None = None, created_from: datetime | None = None, created_to: datetime | None = None, limit: int = 20, offset: int = 0) -> list[Order]:
    stmt = (
        select(Order)
        .options(*_order_load_options())
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(limit)
        .offset(offset)
        .execution_options(populate_existing=True)
    )

    if history_bucket is not None:
        stmt = stmt.where(build_history_bucket_clause(Order, history_bucket))

    if status_code is not None:
        # Filter the same projected state the list displays, including orders
        # created before the processing label was persisted on new orders.
        def job_status(prefix):
            return select(IntegrationRun.status).where(IntegrationRun.idempotency_key ==
                literal(prefix) + cast(Order.id, String)).correlate(Order).scalar_subquery()
        job = func.coalesce(job_status("app:complete-checkout:"), job_status("order:auto:moysklad:"), "")
        active = and_(build_history_bucket_clause(Order, "active"), Order.is_paid.is_(False),
                      Order.is_shipped.is_(False), Order.is_canceled.is_(False))
        processing = and_(active, job.in_(("queued", "running", "retrying")))
        failed = and_(active, job.in_(("error", "canceled")))
        underlying = and_(not_(or_(processing, failed)), build_status_code_clause(Order, status_code))
        stmt = stmt.where(or_(processing, underlying) if status_code == "processing"
                          else or_(failed, underlying) if status_code == "checkout_failed" else underlying)

    if created_from is not None:
        stmt = stmt.where(Order.created_at >= created_from)

    if created_to is not None:
        stmt = stmt.where(Order.created_at <= created_to)

    return list((await session.execute(stmt)).scalars().all())
