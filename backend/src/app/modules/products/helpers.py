from fastapi import Request

from src.database.models import Product
from src.database.schemas import ProductRead, ProductVariantRead, ProductWithVariantsRead
from src.product_media import build_products_media_url

ReviewStatsByProductId = dict[int, tuple[float, int]]


def build_product_image_url(request: Request, product: Product) -> str:
    return build_products_media_url(str(request.base_url), product.image_path)


def build_variant_image_url(request: Request, variant) -> str:
    return build_products_media_url(str(request.base_url), variant.image_path)


def serialize_product_variant(request: Request, variant) -> ProductVariantRead:
    payload = ProductVariantRead.model_validate(variant)
    return payload.model_copy(update={"image_url": build_variant_image_url(request, variant)})


def _get_review_stats(
    product_id: int,
    review_stats_by_product_id: ReviewStatsByProductId | None,
) -> tuple[float, int]:
    if review_stats_by_product_id is None:
        return (0.0, 0)
    return review_stats_by_product_id.get(product_id, (0.0, 0))


def serialize_product(
    request: Request,
    product: Product,
    *,
    review_stats_by_product_id: ReviewStatsByProductId | None = None,
) -> ProductRead:
    payload = ProductRead.model_validate(product)
    rating_avg, rating_count = _get_review_stats(product.id, review_stats_by_product_id)
    return payload.model_copy(
        update={
            "image_url": build_product_image_url(request, product),
            "rating_avg": rating_avg,
            "rating_count": rating_count,
        }
    )


def serialize_product_with_variants(
    request: Request,
    product: Product,
    *,
    review_stats_by_product_id: ReviewStatsByProductId | None = None,
) -> ProductWithVariantsRead:
    payload = ProductWithVariantsRead.model_validate(product)
    variants = [serialize_product_variant(request, variant) for variant in product.variants]
    rating_avg, rating_count = _get_review_stats(product.id, review_stats_by_product_id)
    return payload.model_copy(
        update={
            "image_url": build_product_image_url(request, product),
            "variants": variants,
            "rating_avg": rating_avg,
            "rating_count": rating_count,
        }
    )


def serialize_products(
    request: Request,
    products: list[Product],
    *,
    review_stats_by_product_id: ReviewStatsByProductId | None = None,
) -> list[ProductRead]:
    return [
        serialize_product(request, product, review_stats_by_product_id=review_stats_by_product_id)
        for product in products
    ]


def serialize_products_with_variants(
    request: Request,
    products: list[Product],
    *,
    review_stats_by_product_id: ReviewStatsByProductId | None = None,
) -> list[ProductWithVariantsRead]:
    return [
        serialize_product_with_variants(request, product, review_stats_by_product_id=review_stats_by_product_id)
        for product in products
    ]
