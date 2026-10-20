from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status
from config import ufa_now
from src.app.modules.admin.helpers import ensure_not_stale, serialize_admin_product_question
from src.app.modules.admin.schemas import AdminPage, AdminProductQuestionModerationPayload, AdminProductQuestionRead
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.database import get_db
from src.database.models import Product, ProductQuestion
from .common import admin_content_router


@admin_content_router.get(
    "/questions",
    response_model=AdminPage[AdminProductQuestionRead],
)
async def list_product_questions(question_status: str | None = Query(default=None, alias="status", pattern="^(pending|published|rejected)$",), product_id: int | None = Query(default=None, ge=1), q: str | None = Query(default=None, max_length=120), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db), _: AdminContext = Depends(require_permission("reviews.read")),) -> AdminPage[AdminProductQuestionRead]:
    filters = []
    if question_status == "pending": filters.extend((ProductQuestion.moderated.is_(False), ProductQuestion.rejected_at.is_(None),))
    elif question_status == "published": filters.extend((ProductQuestion.moderated.is_(True), ProductQuestion.rejected_at.is_(None),))
    elif question_status == "rejected": filters.append(ProductQuestion.rejected_at.is_not(None))
    if product_id: filters.append(ProductQuestion.product_id == product_id)
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(ProductQuestion.text.ilike(pattern), ProductQuestion.answer.ilike(pattern), ProductQuestion.guest_name.ilike(pattern), Product.name.ilike(pattern),))
    base_query = (select(ProductQuestion, Product.name).join(Product, Product.id == ProductQuestion.product_id).options(selectinload(ProductQuestion.user)).where(*filters))
    total = int((await db.execute(select(func.count(ProductQuestion.id)).join(Product, Product.id == ProductQuestion.product_id).where(*filters))).scalar_one())
    rows = (await db.execute(base_query.order_by(ProductQuestion.created_at.desc(), ProductQuestion.id.desc()).offset(offset).limit(limit))).all()
    return AdminPage(items=[serialize_admin_product_question(question, product_name=product_name) for question, product_name in rows], total=total, limit=limit, offset=offset,)


@admin_content_router.patch(
    "/questions/{question_id}/moderation",
    response_model=AdminProductQuestionRead,
)
async def moderate_product_question(question_id: int, payload: AdminProductQuestionModerationPayload, request: Request, db: AsyncSession = Depends(get_db), context: AdminContext = Depends(require_permission("reviews.moderate", write=True)),) -> AdminProductQuestionRead:
    row = (await db.execute(select(ProductQuestion, Product.name).join(Product, Product.id == ProductQuestion.product_id).options(selectinload(ProductQuestion.user)).where(ProductQuestion.id == question_id).execution_options(populate_existing=True))).one_or_none()
    if row is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product question not found",)
    question, product_name = row
    ensure_not_stale(
        actual=question.updated_at,
        expected=payload.expected_updated_at,
    )
    before = serialize_admin_product_question(question, product_name=product_name,).model_dump(mode="json")
    now = ufa_now()
    question.answer = payload.answer.strip() if payload.answer else None
    question.internal_moderation_comment = (payload.internal_comment.strip() if payload.internal_comment else None)
    question.moderated_at = now
    question.moderated_by_user_id = context.user.id
    if payload.action == "publish":
        question.moderated = True
        question.rejected_at = None
    else:
        question.moderated = False
        question.rejected_at = now
    await db.flush()
    result = serialize_admin_product_question(question, product_name=product_name,)
    await add_admin_audit(
        db,
        request,
        context,
        action=f"product_question.{payload.action}",
        entity_type="product_question",
        entity_id=question.id,
        before=before,
        after=result.model_dump(mode="json"),
    )
    await db.commit()
    return result
