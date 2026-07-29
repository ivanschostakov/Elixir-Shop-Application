from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models.catalog.product_question import ProductQuestion
from src.database.schemas.catalog.product_question import ProductQuestionCreate


async def get_product_questions(
    session: AsyncSession,
    *,
    product_id: int,
    offset: int = 0,
    limit: int = 100,
    moderated_only: bool = True,
) -> list[ProductQuestion]:
    stmt = (
        select(ProductQuestion)
        .options(selectinload(ProductQuestion.user))
        .where(ProductQuestion.product_id == product_id)
        .order_by(ProductQuestion.created_at.desc(), ProductQuestion.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if moderated_only:
        stmt = stmt.where(
            ProductQuestion.moderated.is_(True),
            ProductQuestion.rejected_at.is_(None),
        )
    return list((await session.execute(stmt)).scalars().all())


async def get_product_question_by_id(
    session: AsyncSession,
    *,
    question_id: int,
) -> ProductQuestion | None:
    stmt = (
        select(ProductQuestion)
        .options(selectinload(ProductQuestion.user))
        .where(ProductQuestion.id == question_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_product_question_count(
    session: AsyncSession,
    *,
    product_id: int,
) -> int:
    stmt = select(func.count(ProductQuestion.id)).where(
        ProductQuestion.product_id == product_id,
        ProductQuestion.moderated.is_(True),
        ProductQuestion.rejected_at.is_(None),
    )
    return int((await session.execute(stmt)).scalar_one())


async def create_product_question(
    session: AsyncSession,
    *,
    user_id: int | None,
    product_id: int,
    data: ProductQuestionCreate,
    guest_name: str | None = None,
) -> ProductQuestion:
    question = ProductQuestion(
        user_id=user_id,
        product_id=product_id,
        guest_name=guest_name,
        text=data.text,
    )
    session.add(question)
    await session.commit()
    await session.refresh(question, attribute_names=["user"])
    return question
