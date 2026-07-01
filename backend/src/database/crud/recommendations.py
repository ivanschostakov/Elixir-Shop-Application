from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import (
    BasketItem,
    FavouredProduct,
    Order,
    OrderItem,
    Product,
    ProductByCategory,
    UserCategoryRecommendationSignal,
    UserProductRecommendationSignal,
)


def _product_price_options():
    return (
        selectinload(Product.variants),
        selectinload(Product.products_by_category).selectinload(ProductByCategory.category),
    )


async def get_or_create_user_product_recommendation_signal(session: AsyncSession, *, user_id: int, product_id: int) -> UserProductRecommendationSignal:
    stmt = (
        select(UserProductRecommendationSignal)
        .where(
            UserProductRecommendationSignal.user_id == user_id,
            UserProductRecommendationSignal.product_id == product_id,
        )
        .with_for_update()
    )
    signal = (await session.execute(stmt)).scalar_one_or_none()
    if signal is not None:
        return signal

    signal = UserProductRecommendationSignal(user_id=user_id, product_id=product_id)
    session.add(signal)
    await session.flush()
    return signal


async def get_or_create_user_category_recommendation_signal(session: AsyncSession, *, user_id: int, category_id: int) -> UserCategoryRecommendationSignal:
    stmt = (
        select(UserCategoryRecommendationSignal)
        .where(
            UserCategoryRecommendationSignal.user_id == user_id,
            UserCategoryRecommendationSignal.category_id == category_id,
        )
        .with_for_update()
    )
    signal = (await session.execute(stmt)).scalar_one_or_none()
    if signal is not None:
        return signal

    signal = UserCategoryRecommendationSignal(user_id=user_id, category_id=category_id)
    session.add(signal)
    await session.flush()
    return signal


async def get_product_category_map_for_products(session: AsyncSession, *, product_ids: Iterable[int]) -> dict[int, set[int]]:
    normalized_ids = {int(product_id) for product_id in product_ids}
    if not normalized_ids:
        return {}

    stmt = select(ProductByCategory.product_id, ProductByCategory.category_id).where(
        ProductByCategory.product_id.in_(normalized_ids)
    )
    rows = (await session.execute(stmt)).all()
    product_categories: dict[int, set[int]] = {product_id: set() for product_id in normalized_ids}
    for product_id, category_id in rows:
        product_categories.setdefault(int(product_id), set()).add(int(category_id))
    return product_categories


async def get_user_product_recommendation_signals(session: AsyncSession, *, user_id: int) -> list[UserProductRecommendationSignal]:
    stmt = (
        select(UserProductRecommendationSignal)
        .where(UserProductRecommendationSignal.user_id == user_id)
        .order_by(UserProductRecommendationSignal.updated_at.desc(), UserProductRecommendationSignal.id.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_user_category_recommendation_signals(session: AsyncSession, *, user_id: int) -> list[UserCategoryRecommendationSignal]:
    stmt = (
        select(UserCategoryRecommendationSignal)
        .where(UserCategoryRecommendationSignal.user_id == user_id)
        .order_by(UserCategoryRecommendationSignal.updated_at.desc(), UserCategoryRecommendationSignal.id.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_user_favourite_rows(session: AsyncSession, *, user_id: int) -> list[FavouredProduct]:
    stmt = (
        select(FavouredProduct)
        .where(FavouredProduct.user_id == user_id)
        .order_by(FavouredProduct.updated_at.desc(), FavouredProduct.id.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_basket_product_ids_for_user(session: AsyncSession, *, user_id: int) -> set[int]:
    stmt = select(BasketItem.product_id).where(BasketItem.user_id == user_id)
    return {int(product_id) for product_id in (await session.execute(stmt)).scalars().all()}


async def get_recently_purchased_product_ids_for_user(session: AsyncSession, *, user_id: int, cutoff: datetime) -> set[int]:
    stmt = (
        select(OrderItem.product_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.user_id == user_id, Order.created_at >= cutoff)
    )
    return {int(product_id) for product_id in (await session.execute(stmt)).scalars().all()}


async def get_candidate_products_for_categories(session: AsyncSession, *, category_ids: Iterable[int], excluded_product_ids: set[int]) -> list[Product]:
    normalized_category_ids = {int(category_id) for category_id in category_ids}
    if not normalized_category_ids:
        return []

    stmt: Select[tuple[Product]] = (
        select(Product)
        .options(*_product_price_options())
        .join(ProductByCategory, ProductByCategory.product_id == Product.id)
        .where(
            ProductByCategory.category_id.in_(normalized_category_ids),
            Product.in_stock.is_(True),
            Product.archived.is_(False),
        )
    )
    if excluded_product_ids:
        stmt = stmt.where(Product.id.notin_(excluded_product_ids))

    return list((await session.execute(stmt)).scalars().unique().all())


async def get_home_fallback_products(session: AsyncSession, *, offset: int, limit: int, excluded_product_ids: set[int]) -> list[Product]:
    stmt: Select[tuple[Product]] = (
        select(Product)
        .options(*_product_price_options())
        .where(Product.in_stock.is_(True), Product.archived.is_(False))
        .order_by(Product.created_at.desc(), Product.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if excluded_product_ids:
        stmt = stmt.where(Product.id.notin_(excluded_product_ids))

    return list((await session.execute(stmt)).scalars().all())
