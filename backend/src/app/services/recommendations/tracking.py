from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import ufa_now
from src.app.services.recommendations.constants import VIEW_DEDUPE_WINDOW
from src.database.crud import get_product_by_id, get_product_category_by_id, get_variant_by_id
from src.database.crud.recommendations import get_or_create_user_category_recommendation_signal, get_or_create_user_product_recommendation_signal


async def record_product_view(session: AsyncSession, *, user_id: int, product_id: int, variant_id: int | None = None) -> None:
    product = await get_product_by_id(session, product_id, include_out_of_stock=True)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if variant_id is not None:
        variant = await get_variant_by_id(session, variant_id, include_archived=True)
        if variant is None or variant.product_id != product.id: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    signal = await get_or_create_user_product_recommendation_signal(session, user_id=user_id, product_id=product.id)
    now = ufa_now()
    if signal.last_viewed_at is not None and now - signal.last_viewed_at <= VIEW_DEDUPE_WINDOW: return

    signal.view_count += 1
    signal.last_viewed_at = now
    await session.commit()


async def record_category_view(session: AsyncSession, *, user_id: int, category_id: int) -> None:
    category = await get_product_category_by_id(session, category_id)
    if category is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    signal = await get_or_create_user_category_recommendation_signal(session, user_id=user_id, category_id=category.id)
    now = ufa_now()
    if signal.last_viewed_at is not None and now - signal.last_viewed_at <= VIEW_DEDUPE_WINDOW: return
    signal.view_count += 1
    signal.last_viewed_at = now
    await session.commit()


async def record_cart_add(session: AsyncSession, *, user_id: int, product_id: int, quantity: int, commit: bool = True) -> None:
    if quantity <= 0: return
    signal = await get_or_create_user_product_recommendation_signal(session, user_id=user_id, product_id=product_id)
    signal.cart_quantity += quantity
    signal.last_carted_at = ufa_now()
    await session.flush()
    if commit: await session.commit()


async def record_purchase(session: AsyncSession, *, user_id: int, product_id: int, quantity: int, commit: bool = True) -> None:
    if quantity <= 0: return
    signal = await get_or_create_user_product_recommendation_signal(session, user_id=user_id, product_id=product_id)
    signal.purchase_quantity += quantity
    signal.last_purchased_at = ufa_now()
    await session.flush()
    if commit: await session.commit()
