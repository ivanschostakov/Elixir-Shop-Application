from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import ufa_now
from src.app.services.recommendations.affinity import build_category_affinity, merge_surface_category_ids, rank_candidate_products, sort_category_ids
from src.app.services.recommendations.constants import DEFAULT_RECOMMENDATION_LIMIT, HOME_CATEGORY_LIMIT, HOME_RECOMMENDATION_LIMIT, RECENT_PURCHASE_WINDOW
from src.app.services.recommendations.types import CategoryAffinity, RecommendationSurface
from src.database.crud import get_order_draft_by_id, get_product_by_id
from src.database.crud.recommendations import (
    get_basket_product_ids_for_user,
    get_candidate_products_for_categories,
    get_home_fallback_products,
    get_product_category_map_for_products,
    get_recently_purchased_product_ids_for_user,
    get_user_category_recommendation_signals,
    get_user_favourite_rows,
    get_user_product_recommendation_signals,
)
from src.database.models import Product


def _limit(surface: RecommendationSurface, requested: int | None) -> int:
    default = HOME_RECOMMENDATION_LIMIT if surface == "home" else DEFAULT_RECOMMENDATION_LIMIT
    return default if requested is None else min(requested, default)


async def _product_categories(session: AsyncSession, product_id: int) -> list[int]:
    product = await get_product_by_id(session, product_id, include_out_of_stock=True)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    categories = await get_product_category_map_for_products(session, product_ids={product_id})
    return sort_category_ids(categories.get(product_id, set()), category_affinity={})


async def _draft_product_ids(session: AsyncSession, user_id: int, draft_id: int) -> set[int]:
    draft = await get_order_draft_by_id(session, draft_id, user_id=user_id)
    if draft is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")
    return {item.product_id for item in draft.items}


async def _categories_for_products(session: AsyncSession, product_ids: set[int]) -> set[int]:
    categories = await get_product_category_map_for_products(session, product_ids=product_ids)
    return {category_id for ids in categories.values() for category_id in ids}


async def _target_categories(session: AsyncSession, *, user_id: int, surface: RecommendationSurface, category_affinity: dict[int, CategoryAffinity], user_top_categories: list[int], product_id: int | None, draft_id: int | None) -> list[int]:
    if surface == "home": return user_top_categories[:HOME_CATEGORY_LIMIT]

    if surface == "product":
        if product_id is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="product_id is required")
        product_categories = await _product_categories(session, product_id)
        overlap = [category_id for category_id in user_top_categories if category_id in set(product_categories)]
        return overlap or sort_category_ids(product_categories, category_affinity=category_affinity)

    if surface == "cart": product_ids = await get_basket_product_ids_for_user(session, user_id=user_id)
    else:
        if draft_id is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="draft_id is required")
        product_ids = await _draft_product_ids(session, user_id, draft_id)

    surface_categories = await _categories_for_products(session, product_ids)
    return merge_surface_category_ids(surface_category_ids=surface_categories, user_top_categories=user_top_categories, category_affinity=category_affinity)


async def _excluded_ids(session: AsyncSession, *, user_id: int, surface: RecommendationSurface, product_id: int | None, draft_id: int | None) -> set[int]:
    ids = await get_basket_product_ids_for_user(session, user_id=user_id)
    ids.update(await get_recently_purchased_product_ids_for_user(session, user_id=user_id, cutoff=ufa_now() - RECENT_PURCHASE_WINDOW))

    if surface == "product" and product_id is not None: ids.add(product_id)
    if surface == "draft" and draft_id is not None: ids.update(await _draft_product_ids(session, user_id, draft_id))
    return ids


async def _home_page(session: AsyncSession, *, ranked: list[Product], offset: int, limit: int, excluded: set[int]) -> list[Product]:
    if limit < 1: return []
    ranked_ids = {product.id for product in ranked}
    excluded = excluded | ranked_ids
    if offset >= len(ranked): return await get_home_fallback_products(session, offset=offset - len(ranked), limit=limit, excluded_product_ids=excluded)
    page = ranked[offset:offset + limit]
    if len(page) >= limit: return page
    page.extend(await get_home_fallback_products(session, offset=0, limit=limit - len(page), excluded_product_ids=excluded))
    return page


async def _affinity(session: AsyncSession, user_id: int):
    product_signals = await get_user_product_recommendation_signals(session, user_id=user_id)
    favourites = await get_user_favourite_rows(session, user_id=user_id)
    category_signals = await get_user_category_recommendation_signals(session, user_id=user_id)

    source_ids = {row.product_id for row in product_signals}
    source_ids.update(row.product_id for row in favourites)

    categories = await get_product_category_map_for_products(session, product_ids=source_ids)
    affinity = build_category_affinity(
        product_signals=product_signals, favourite_rows=favourites, category_signals=category_signals, categories_by_product_id=categories,
    )
    return affinity, source_ids, sort_category_ids(affinity.keys(), category_affinity=affinity)


async def get_recommended_products_for_user(session: AsyncSession, *, user_id: int, surface: RecommendationSurface, product_id: int | None = None, draft_id: int | None = None, limit: int | None = None, offset: int = 0) -> list[Product]:
    limit, offset = _limit(surface, limit), max(offset, 0)
    if limit < 1: return []

    category_affinity, source_ids, user_top_categories = await _affinity(session, user_id)
    excluded = await _excluded_ids(session, user_id=user_id, surface=surface, product_id=product_id, draft_id=draft_id)
    excluded.update(source_ids)

    if surface == "home" and not user_top_categories: return await _home_page(session, ranked=[], offset=offset, limit=limit, excluded=excluded)
    target_categories = await _target_categories(session, user_id=user_id, surface=surface, category_affinity=category_affinity, user_top_categories=user_top_categories, product_id=product_id, draft_id=draft_id)

    if not target_categories: return await _home_page(session, ranked=[], offset=offset, limit=limit, excluded=excluded) if surface == "home" else []
    candidates = await get_candidate_products_for_categories(session, category_ids=target_categories, excluded_product_ids=excluded) 
    candidate_categories = await get_product_category_map_for_products(session, product_ids={product.id for product in candidates})
    ranked = rank_candidate_products(candidates, category_ids=target_categories, categories_by_product_id=candidate_categories, category_affinity=category_affinity)

    if surface == "home": return await _home_page(session, ranked=ranked, offset=offset, limit=limit, excluded=excluded)
    return ranked[offset:offset + limit]