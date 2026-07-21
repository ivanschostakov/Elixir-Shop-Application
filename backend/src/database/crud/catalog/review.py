from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models.orders.order import Order
from src.database.models.orders.order_item import OrderItem
from src.database.models.catalog.review import Review
from src.database.models.catalog.review_attachment import ReviewAttachment
from src.database.schemas import ReviewCreate


async def get_product_reviews(session: AsyncSession, *, product_id: int, offset: int = 0, limit: int = 20, moderated_only: bool = True) -> list[Review]:
    stmt = (
        select(Review)
        .options(
            selectinload(Review.user),
            selectinload(Review.attachments),
        )
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc(), Review.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if moderated_only:
        stmt = stmt.where(Review.moderated.is_(True), Review.rejected_at.is_(None))
    return list((await session.execute(stmt)).scalars().all())


async def get_review_by_id(session: AsyncSession, *, review_id: int) -> Review | None:
    stmt = (
        select(Review)
        .options(
            selectinload(Review.user),
            selectinload(Review.attachments),
        )
        .where(Review.id == review_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_product_review(session: AsyncSession, *, user_id: int | None, product_id: int, data: ReviewCreate, commit: bool = True) -> Review:
    review = Review(
        user_id=user_id,
        product_id=product_id,
        value=data.value,
        text=data.text,
        guest_name=data.guest_name,
        guest_email=str(data.guest_email) if data.guest_email else None,
    )
    session.add(review)
    await session.flush()
    if commit:
        await session.commit()
    await session.refresh(review, attribute_names=["user", "attachments"])
    return review


async def create_review_attachment(session: AsyncSession, *, review_id: int, filename: str, mime_type: str | None, commit: bool = False) -> ReviewAttachment:
    attachment = ReviewAttachment(
        review_id=review_id,
        filename=filename,
        mime_type=mime_type,
    )
    session.add(attachment)
    await session.flush()
    if commit:
        await session.commit()
    await session.refresh(attachment)
    return attachment


async def has_user_purchased_product(session: AsyncSession, *, user_id: int, product_id: int) -> bool:
    stmt = (
        select(OrderItem.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.user_id == user_id,
            OrderItem.product_id == product_id,
            Order.is_paid.is_(True),
            Order.is_canceled.is_(False),
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def get_product_review_stats(session: AsyncSession, *, product_ids: list[int]) -> dict[int, tuple[float, int]]:
    if not product_ids:
        return {}

    stmt = (
        select(
            Review.product_id,
            func.avg(Review.value).label("rating_avg"),
            func.count(Review.id).label("rating_count"),
        )
        .where(Review.product_id.in_(product_ids), Review.moderated.is_(True), Review.rejected_at.is_(None))
        .group_by(Review.product_id)
    )
    rows = (await session.execute(stmt)).all()
    return {
        int(product_id): (float(rating_avg or 0.0), int(rating_count or 0))
        for product_id, rating_avg, rating_count in rows
    }
