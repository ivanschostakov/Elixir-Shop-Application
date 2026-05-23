from datetime import datetime
from typing import Iterable

from src.app.services.recommendations.constants import (
    CART_SIGNAL_WEIGHT,
    CATEGORY_OVERLAP_WEIGHT,
    CATEGORY_VIEW_SIGNAL_WEIGHT,
    FAVORITE_SIGNAL_WEIGHT,
    PURCHASE_SIGNAL_WEIGHT,
    VIEW_SIGNAL_WEIGHT,
)
from src.app.services.recommendations.types import CategoryAffinity
from src.database.models import FavouredProduct, Product, UserCategoryRecommendationSignal, UserProductRecommendationSignal


def resolve_signal_last_touched(signal: UserProductRecommendationSignal) -> datetime | None:
    timestamps = [signal.last_viewed_at, signal.last_carted_at, signal.last_purchased_at]
    return max((timestamp for timestamp in timestamps if timestamp is not None), default=None)


def merge_last_timestamp(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if current is None: return candidate
    if candidate is None: return current
    return max(current, candidate)


def timestamp_sort_key(value: datetime | None) -> float:
    if value is None: return float("-inf")
    return value.timestamp()


def apply_category_affinity_signal(category_affinity: dict[int, CategoryAffinity], *, category_id: int, score: int, last_signal_at: datetime | None) -> None:
    if score <= 0: return

    current = category_affinity.get(category_id)
    if current is None:
        category_affinity[category_id] = CategoryAffinity(score=score, last_signal_at=last_signal_at)
        return

    current.score += score
    current.last_signal_at = merge_last_timestamp(current.last_signal_at, last_signal_at)


def build_category_affinity(product_signals: list[UserProductRecommendationSignal], favourite_rows: list[FavouredProduct], category_signals: list[UserCategoryRecommendationSignal], *, categories_by_product_id: dict[int, set[int]]) -> dict[int, CategoryAffinity]:
    category_affinity: dict[int, CategoryAffinity] = {}
    for signal in product_signals:
        category_ids = categories_by_product_id.get(signal.product_id, set())
        if not category_ids: continue
        signal_score = signal.purchase_quantity * PURCHASE_SIGNAL_WEIGHT + signal.cart_quantity * CART_SIGNAL_WEIGHT + signal.view_count * VIEW_SIGNAL_WEIGHT
        signal_last_touched = resolve_signal_last_touched(signal)
        for category_id in category_ids: apply_category_affinity_signal(category_affinity, category_id=category_id, score=signal_score, last_signal_at=signal_last_touched)

    for favourite in favourite_rows:
        category_ids = categories_by_product_id.get(favourite.product_id, set())
        if not category_ids: continue
        for category_id in category_ids: apply_category_affinity_signal(category_affinity, category_id=category_id, score=FAVORITE_SIGNAL_WEIGHT, last_signal_at=favourite.updated_at)

    for category_signal in category_signals: apply_category_affinity_signal(category_affinity, category_id=category_signal.category_id, score=category_signal.view_count * CATEGORY_VIEW_SIGNAL_WEIGHT, last_signal_at=category_signal.last_viewed_at)
    return category_affinity


def sort_category_ids(category_ids: Iterable[int], *, category_affinity: dict[int, CategoryAffinity]) -> list[int]:
    normalized_ids = list({int(category_id) for category_id in category_ids})
    return sorted(normalized_ids, key=lambda category_id: (-category_affinity.get(category_id, CategoryAffinity()).score, -timestamp_sort_key(category_affinity.get(category_id, CategoryAffinity()).last_signal_at), category_id))


def merge_surface_category_ids(surface_category_ids: Iterable[int], user_top_categories: Iterable[int], category_affinity: dict[int, CategoryAffinity]) -> list[int]:
    merged_category_ids = {int(category_id) for category_id in surface_category_ids}
    merged_category_ids.update(int(category_id) for category_id in user_top_categories)
    return sort_category_ids(merged_category_ids, category_affinity=category_affinity)


def rank_candidate_products(products: list[Product], category_ids: Iterable[int], categories_by_product_id: dict[int, set[int]], category_affinity: dict[int, CategoryAffinity]) -> list[Product]:
    target_category_ids = {int(category_id) for category_id in category_ids}
    def sort_key(product: Product) -> tuple[float, int, float, int, float, int]:
        shared_category_ids = categories_by_product_id.get(product.id, set()) & target_category_ids
        shared_category_count = len(shared_category_ids)
        product_score = sum(category_affinity.get(category_id, CategoryAffinity()).score for category_id in shared_category_ids) + shared_category_count * CATEGORY_OVERLAP_WEIGHT
        product_last_signal_at = max((category_affinity.get(category_id, CategoryAffinity()).last_signal_at for category_id in shared_category_ids if category_affinity.get(category_id, CategoryAffinity()).last_signal_at is not None), default=None)
        return -float(product_score), -shared_category_count, -timestamp_sort_key(product_last_signal_at), -(product.priority or 0), -product.created_at.timestamp(), -product.id

    return sorted(products, key=sort_key)

