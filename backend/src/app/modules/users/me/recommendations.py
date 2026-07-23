from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.products.helpers import get_user_product_price_discount_context, serialize_products_with_variants
from src.app.modules.users.me.schemas import RecommendationCategoryViewPayload, RecommendationSurface, RecommendationViewPayload
from src.app.services.recommendations import (
    get_recommended_products_for_user,
    record_category_view,
    record_product_view,
)
from src.app.services.customer_intelligence import record_customer_event_safe
from src.database import get_db
from src.database.models import User
from src.database.schemas import ProductWithVariantsRead

recommendations_router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@recommendations_router.post("/views", status_code=status.HTTP_204_NO_CONTENT)
async def create_my_recommendation_view(payload: RecommendationViewPayload, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    await record_product_view(db, user_id=current_user.id, product_id=payload.product_id, variant_id=payload.variant_id)
    await record_customer_event_safe(
        db,
        user_id=current_user.id,
        event_name="product_viewed",
        entity_type="product",
        entity_id=payload.product_id,
        properties={"variant_id": payload.variant_id},
        commit=True,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@recommendations_router.post("/categories/views", status_code=status.HTTP_204_NO_CONTENT)
async def create_my_recommendation_category_view(payload: RecommendationCategoryViewPayload, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    await record_category_view(db, user_id=current_user.id, category_id=payload.category_id)
    await record_customer_event_safe(
        db,
        user_id=current_user.id,
        event_name="category_viewed",
        entity_type="category",
        entity_id=payload.category_id,
        commit=True,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@recommendations_router.get("", response_model=list[ProductWithVariantsRead], status_code=status.HTTP_200_OK)
async def list_my_recommendations(request: Request, surface: RecommendationSurface = Query(...), product_id: int | None = Query(default=None, ge=1), draft_id: int | None = Query(default=None, ge=1), limit: int | None = Query(default=None, ge=1, le=20), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ProductWithVariantsRead]:
    products = await get_recommended_products_for_user(db, user_id=current_user.id, surface=surface, product_id=product_id, draft_id=draft_id, limit=limit, offset=offset)
    discount_context = await get_user_product_price_discount_context(db, current_user)
    return serialize_products_with_variants(request, products, discount_context=discount_context)
