from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Literal

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from config import ufa_now
from src.database.crud import get_order_draft_by_id, get_product_by_id, get_product_category_by_id
from src.database.models import (
    BasketItem,
    FavouredProduct,
    Order,
    OrderItem,
    Product,
    ProductByCategory,
    UserCategoryRecommendationSignal,
    UserProductRecommendationSignal,
    Variant,
)

RecommendationSurface = Literal["home", "product", "cart", "draft"]

HOME_RECOMMENDATION_LIMIT = 8
DEFAULT_RECOMMENDATION_LIMIT = 6
HOME_CATEGORY_LIMIT = 3
VIEW_DEDUPE_WINDOW = timedelta(minutes=30)
RECENT_PURCHASE_WINDOW = timedelta(days=30)
PURCHASE_SIGNAL_WEIGHT = 12
FAVORITE_SIGNAL_WEIGHT = 8
CART_SIGNAL_WEIGHT = 6
CATEGORY_VIEW_SIGNAL_WEIGHT = 4
VIEW_SIGNAL_WEIGHT = 2
CATEGORY_OVERLAP_WEIGHT = 1


@dataclass(slots=True)
class CategoryAffinity:
    score: int = 0
    last_signal_at: datetime | None = None


def _resolve_limit(surface: RecommendationSurface, requested_limit: int | None) -> int:
    default_limit = HOME_RECOMMENDATION_LIMIT if surface == "home" else DEFAULT_RECOMMENDATION_LIMIT
    if requested_limit is None:
        return default_limit
    return min(requested_limit, default_limit)


def _resolve_signal_last_touched(signal: UserProductRecommendationSignal) -> datetime | None:
    timestamps = [
        signal.last_viewed_at,
        signal.last_carted_at,
        signal.last_purchased_at,
    ]
    return max((timestamp for timestamp in timestamps if timestamp is not None), default=None)


def _merge_last_timestamp(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if current is None:
        return candidate
    if candidate is None:
        return current
    return max(current, candidate)


def _timestamp_sort_key(value: datetime | None) -> float:
    if value is None:
        return float("-inf")
    return value.timestamp()


async def _get_or_create_signal(
    session: AsyncSession,
    *,
    user_id: int,
    product_id: int,
) -> UserProductRecommendationSignal:
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

    signal = UserProductRecommendationSignal(
        user_id=user_id,
        product_id=product_id,
    )
    session.add(signal)
    await session.flush()
    return signal


async def _get_or_create_category_signal(
    session: AsyncSession,
    *,
    user_id: int,
    category_id: int,
) -> UserCategoryRecommendationSignal:
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

    signal = UserCategoryRecommendationSignal(
        user_id=user_id,
        category_id=category_id,
    )
    session.add(signal)
    await session.flush()
    return signal


async def _load_product_categories_by_product_id(
    session: AsyncSession,
    *,
    product_ids: Iterable[int],
) -> dict[int, set[int]]:
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


async def _load_signal_rows(
    session: AsyncSession,
    *,
    user_id: int,
) -> list[UserProductRecommendationSignal]:
    stmt = (
        select(UserProductRecommendationSignal)
        .where(UserProductRecommendationSignal.user_id == user_id)
        .order_by(UserProductRecommendationSignal.updated_at.desc(), UserProductRecommendationSignal.id.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def _load_category_signal_rows(
    session: AsyncSession,
    *,
    user_id: int,
) -> list[UserCategoryRecommendationSignal]:
    stmt = (
        select(UserCategoryRecommendationSignal)
        .where(UserCategoryRecommendationSignal.user_id == user_id)
        .order_by(
            UserCategoryRecommendationSignal.updated_at.desc(),
            UserCategoryRecommendationSignal.id.desc(),
        )
    )
    return list((await session.execute(stmt)).scalars().all())


async def _load_favourite_rows(
    session: AsyncSession,
    *,
    user_id: int,
) -> list[FavouredProduct]:
    stmt = (
        select(FavouredProduct)
        .where(FavouredProduct.user_id == user_id)
        .order_by(FavouredProduct.updated_at.desc(), FavouredProduct.id.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


def _apply_category_affinity_signal(
    category_affinity: dict[int, CategoryAffinity],
    *,
    category_id: int,
    score: int,
    last_signal_at: datetime | None,
) -> None:
    if score <= 0:
        return

    current = category_affinity.get(category_id)
    if current is None:
        category_affinity[category_id] = CategoryAffinity(
            score=score,
            last_signal_at=last_signal_at,
        )
        return

    current.score += score
    current.last_signal_at = _merge_last_timestamp(current.last_signal_at, last_signal_at)


def _build_category_affinity(
    product_signals: list[UserProductRecommendationSignal],
    favourite_rows: list[FavouredProduct],
    category_signals: list[UserCategoryRecommendationSignal],
    *,
    categories_by_product_id: dict[int, set[int]],
) -> dict[int, CategoryAffinity]:
    category_affinity: dict[int, CategoryAffinity] = {}

    for signal in product_signals:
        category_ids = categories_by_product_id.get(signal.product_id, set())
        if not category_ids:
            continue

        signal_last_touched = _resolve_signal_last_touched(signal)
        signal_score = (
            signal.purchase_quantity * PURCHASE_SIGNAL_WEIGHT
            + signal.cart_quantity * CART_SIGNAL_WEIGHT
            + signal.view_count * VIEW_SIGNAL_WEIGHT
        )
        for category_id in category_ids:
            _apply_category_affinity_signal(
                category_affinity,
                category_id=category_id,
                score=signal_score,
                last_signal_at=signal_last_touched,
            )

    for favourite in favourite_rows:
        category_ids = categories_by_product_id.get(favourite.product_id, set())
        if not category_ids:
            continue

        for category_id in category_ids:
            _apply_category_affinity_signal(
                category_affinity,
                category_id=category_id,
                score=FAVORITE_SIGNAL_WEIGHT,
                last_signal_at=favourite.updated_at,
            )

    for category_signal in category_signals:
        _apply_category_affinity_signal(
            category_affinity,
            category_id=category_signal.category_id,
            score=category_signal.view_count * CATEGORY_VIEW_SIGNAL_WEIGHT,
            last_signal_at=category_signal.last_viewed_at,
        )

    return category_affinity


def _sort_category_ids(
    category_ids: Iterable[int],
    *,
    category_affinity: dict[int, CategoryAffinity],
) -> list[int]:
    normalized_ids = list({int(category_id) for category_id in category_ids})
    return sorted(
        normalized_ids,
        key=lambda category_id: (
            -category_affinity.get(category_id, CategoryAffinity()).score,
            -_timestamp_sort_key(category_affinity.get(category_id, CategoryAffinity()).last_signal_at),
            category_id,
        ),
    )


def _merge_surface_category_ids(
    *,
    surface_category_ids: Iterable[int],
    user_top_categories: Iterable[int],
    category_affinity: dict[int, CategoryAffinity],
) -> list[int]:
    merged_category_ids = {
        int(category_id)
        for category_id in surface_category_ids
    }
    merged_category_ids.update(int(category_id) for category_id in user_top_categories)
    return _sort_category_ids(merged_category_ids, category_affinity=category_affinity)


async def _load_basket_product_ids(
    session: AsyncSession,
    *,
    user_id: int,
) -> set[int]:
    stmt = select(BasketItem.product_id).where(BasketItem.user_id == user_id)
    return {int(product_id) for product_id in (await session.execute(stmt)).scalars().all()}


async def _load_recently_purchased_product_ids(
    session: AsyncSession,
    *,
    user_id: int,
) -> set[int]:
    cutoff = ufa_now() - RECENT_PURCHASE_WINDOW
    stmt = (
        select(OrderItem.product_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.user_id == user_id, Order.created_at >= cutoff)
    )
    return {int(product_id) for product_id in (await session.execute(stmt)).scalars().all()}


async def _load_current_product_or_404(session: AsyncSession, *, product_id: int) -> Product:
    product = await get_product_by_id(session, product_id, include_out_of_stock=True)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


async def _load_product_categories_or_404(session: AsyncSession, *, product_id: int) -> list[int]:
    await _load_current_product_or_404(session, product_id=product_id)
    categories_by_product_id = await _load_product_categories_by_product_id(session, product_ids={product_id})
    return _sort_category_ids(categories_by_product_id.get(product_id, set()), category_affinity={})


async def _load_target_categories_for_surface(
    session: AsyncSession,
    *,
    user_id: int,
    surface: RecommendationSurface,
    category_affinity: dict[int, CategoryAffinity],
    user_top_categories: list[int],
    product_id: int | None,
    draft_id: int | None,
) -> list[int]:
    if surface == "home":
        return user_top_categories[:HOME_CATEGORY_LIMIT]

    if surface == "product":
        if product_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="product_id is required")

        current_product_categories = await _load_product_categories_or_404(session, product_id=product_id)
        if not current_product_categories:
            return []

        overlapping_categories = [
            category_id
            for category_id in user_top_categories
            if category_id in set(current_product_categories)
        ]
        if overlapping_categories:
            return overlapping_categories

        return _sort_category_ids(current_product_categories, category_affinity=category_affinity)

    if surface == "cart":
        basket_product_ids = await _load_basket_product_ids(session, user_id=user_id)
        categories_by_product_id = await _load_product_categories_by_product_id(
            session,
            product_ids=basket_product_ids,
        )
        basket_category_ids = {
            category_id
            for category_ids in categories_by_product_id.values()
            for category_id in category_ids
        }
        return _merge_surface_category_ids(
            surface_category_ids=basket_category_ids,
            user_top_categories=user_top_categories,
            category_affinity=category_affinity,
        )

    if draft_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="draft_id is required")

    draft = await get_order_draft_by_id(session, draft_id, user_id=user_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")

    draft_product_ids = {item.product_id for item in draft.items}
    categories_by_product_id = await _load_product_categories_by_product_id(
        session,
        product_ids=draft_product_ids,
    )
    draft_category_ids = {
        category_id
        for category_ids in categories_by_product_id.values()
        for category_id in category_ids
    }
    return _merge_surface_category_ids(
        surface_category_ids=draft_category_ids,
        user_top_categories=user_top_categories,
        category_affinity=category_affinity,
    )


async def _load_excluded_product_ids(
    session: AsyncSession,
    *,
    user_id: int,
    surface: RecommendationSurface,
    product_id: int | None,
    draft_id: int | None,
) -> set[int]:
    excluded_product_ids = await _load_basket_product_ids(session, user_id=user_id)
    excluded_product_ids.update(
        await _load_recently_purchased_product_ids(session, user_id=user_id)
    )

    if surface == "product" and product_id is not None:
        excluded_product_ids.add(product_id)

    if surface == "draft" and draft_id is not None:
        draft = await get_order_draft_by_id(session, draft_id, user_id=user_id)
        if draft is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")
        excluded_product_ids.update(item.product_id for item in draft.items)

    return excluded_product_ids


async def _load_candidate_products(
    session: AsyncSession,
    *,
    category_ids: Iterable[int],
    excluded_product_ids: set[int],
) -> list[Product]:
    normalized_category_ids = {int(category_id) for category_id in category_ids}
    if not normalized_category_ids:
        return []

    stmt: Select[tuple[Product]] = (
        select(Product)
        .options(selectinload(Product.variants))
        .join(ProductByCategory, ProductByCategory.product_id == Product.id)
        .where(ProductByCategory.category_id.in_(normalized_category_ids), Product.in_stock.is_(True))
    )
    if excluded_product_ids:
        stmt = stmt.where(Product.id.notin_(excluded_product_ids))

    return list((await session.execute(stmt)).scalars().unique().all())


def _rank_candidate_products(
    products: list[Product],
    *,
    category_ids: Iterable[int],
    categories_by_product_id: dict[int, set[int]],
    category_affinity: dict[int, CategoryAffinity],
) -> list[Product]:
    target_category_ids = {int(category_id) for category_id in category_ids}

    def sort_key(product: Product) -> tuple[float, int, float, int, float, int]:
        shared_category_ids = categories_by_product_id.get(product.id, set()) & target_category_ids
        shared_category_count = len(shared_category_ids)
        product_score = (
            sum(category_affinity.get(category_id, CategoryAffinity()).score for category_id in shared_category_ids)
            + shared_category_count * CATEGORY_OVERLAP_WEIGHT
        )
        product_last_signal_at = max(
            (
                category_affinity.get(category_id, CategoryAffinity()).last_signal_at
                for category_id in shared_category_ids
                if category_affinity.get(category_id, CategoryAffinity()).last_signal_at is not None
            ),
            default=None,
        )
        return (
            -float(product_score),
            -shared_category_count,
            -_timestamp_sort_key(product_last_signal_at),
            -(product.priority or 0),
            -product.created_at.timestamp(),
            -product.id,
        )

    return sorted(products, key=sort_key)


async def _load_home_fallback_products(
    session: AsyncSession,
    *,
    offset: int,
    limit: int,
    excluded_product_ids: set[int],
) -> list[Product]:
    stmt: Select[tuple[Product]] = (
        select(Product)
        .options(selectinload(Product.variants))
        .where(Product.in_stock.is_(True))
        .order_by(Product.created_at.desc(), Product.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if excluded_product_ids:
        stmt = stmt.where(Product.id.notin_(excluded_product_ids))
    return list((await session.execute(stmt)).scalars().all())


async def record_product_view(
    session: AsyncSession,
    *,
    user_id: int,
    product_id: int,
    variant_id: int | None = None,
) -> None:
    product = await get_product_by_id(session, product_id, include_out_of_stock=True)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    if variant_id is not None:
        variant = await session.get(Variant, variant_id)
        if variant is None or variant.product_id != product.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    signal = await _get_or_create_signal(session, user_id=user_id, product_id=product.id)
    now = ufa_now()
    if signal.last_viewed_at is not None and now - signal.last_viewed_at <= VIEW_DEDUPE_WINDOW:
        return

    signal.view_count += 1
    signal.last_viewed_at = now
    await session.commit()


async def record_category_view(
    session: AsyncSession,
    *,
    user_id: int,
    category_id: int,
) -> None:
    category = await get_product_category_by_id(session, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    signal = await _get_or_create_category_signal(session, user_id=user_id, category_id=category.id)
    now = ufa_now()
    if signal.last_viewed_at is not None and now - signal.last_viewed_at <= VIEW_DEDUPE_WINDOW:
        return

    signal.view_count += 1
    signal.last_viewed_at = now
    await session.commit()


async def record_cart_add(
    session: AsyncSession,
    *,
    user_id: int,
    product_id: int,
    quantity: int,
    commit: bool = True,
) -> None:
    if quantity <= 0:
        return

    signal = await _get_or_create_signal(session, user_id=user_id, product_id=product_id)
    signal.cart_quantity += quantity
    signal.last_carted_at = ufa_now()
    await session.flush()

    if commit:
        await session.commit()


async def record_purchase(
    session: AsyncSession,
    *,
    user_id: int,
    product_id: int,
    quantity: int,
    commit: bool = True,
) -> None:
    if quantity <= 0:
        return

    signal = await _get_or_create_signal(session, user_id=user_id, product_id=product_id)
    signal.purchase_quantity += quantity
    signal.last_purchased_at = ufa_now()
    await session.flush()

    if commit:
        await session.commit()


async def get_recommended_products_for_user(
    session: AsyncSession,
    *,
    user_id: int,
    surface: RecommendationSurface,
    product_id: int | None = None,
    draft_id: int | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Product]:
    resolved_limit = _resolve_limit(surface, limit)
    if resolved_limit < 1:
        return []
    resolved_offset = max(offset, 0)

    product_signal_rows = await _load_signal_rows(session, user_id=user_id)
    favourite_rows = await _load_favourite_rows(session, user_id=user_id)
    category_signal_rows = await _load_category_signal_rows(session, user_id=user_id)

    source_product_ids = {signal.product_id for signal in product_signal_rows}
    source_product_ids.update(favourite.product_id for favourite in favourite_rows)
    source_categories_by_product_id = await _load_product_categories_by_product_id(
        session,
        product_ids=source_product_ids,
    )
    category_affinity = _build_category_affinity(
        product_signals=product_signal_rows,
        favourite_rows=favourite_rows,
        category_signals=category_signal_rows,
        categories_by_product_id=source_categories_by_product_id,
    )
    user_top_categories = _sort_category_ids(
        category_affinity.keys(),
        category_affinity=category_affinity,
    )

    excluded_product_ids = await _load_excluded_product_ids(
        session,
        user_id=user_id,
        surface=surface,
        product_id=product_id,
        draft_id=draft_id,
    )
    excluded_product_ids.update(source_product_ids)

    if surface == "home" and not user_top_categories:
        return await _load_home_fallback_products(
            session,
            offset=resolved_offset,
            limit=resolved_limit,
            excluded_product_ids=excluded_product_ids,
        )

    target_category_ids = await _load_target_categories_for_surface(
        session,
        user_id=user_id,
        surface=surface,
        category_affinity=category_affinity,
        user_top_categories=user_top_categories,
        product_id=product_id,
        draft_id=draft_id,
    )
    if not target_category_ids:
        return []

    candidate_products = await _load_candidate_products(
        session,
        category_ids=target_category_ids,
        excluded_product_ids=excluded_product_ids,
    )
    if not candidate_products:
        return []

    candidate_categories_by_product_id = await _load_product_categories_by_product_id(
        session,
        product_ids={product.id for product in candidate_products},
    )
    ranked_products = _rank_candidate_products(
        candidate_products,
        category_ids=target_category_ids,
        categories_by_product_id=candidate_categories_by_product_id,
        category_affinity=category_affinity,
    )
    return ranked_products[resolved_offset:resolved_offset + resolved_limit]
