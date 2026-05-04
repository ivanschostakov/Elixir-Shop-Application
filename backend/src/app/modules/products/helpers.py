from pathlib import Path

from fastapi import Request

from config import REVIEWS_MEDIA_DIR
from src.app.services.review_attachments import build_review_attachment_url
from src.database.models import Product, Review
from src.database.schemas import ProductRead, ProductVariantRead, ProductWithVariantsRead, ReviewAttachmentRead, ReviewRead
from src.product_media import build_products_media_url

ReviewStatsByProductId = dict[int, tuple[float, int]]
PLACEHOLDER_SITE_REVIEW_AUTHOR = "С сайта"


def build_product_image_url(request: Request, product: Product) -> str:
    return build_products_media_url(str(request.base_url), product.image_path)


def build_variant_image_url(request: Request, variant) -> str:
    return build_products_media_url(str(request.base_url), variant.image_path)


def build_review_attachment_path(review_id: int, filename: str) -> Path:
    return REVIEWS_MEDIA_DIR / str(review_id) / filename


def serialize_product_variant(request: Request, variant) -> ProductVariantRead:
    payload = ProductVariantRead.model_validate(variant)
    return payload.model_copy(update={"image_url": build_variant_image_url(request, variant)})


def _get_review_stats(product_id: int, review_stats_by_product_id: ReviewStatsByProductId | None) -> tuple[float, int]:
    if review_stats_by_product_id is None: return (0.0, 0)
    return review_stats_by_product_id.get(product_id, (0.0, 0))


def serialize_product(request: Request, product: Product, *, review_stats_by_product_id: ReviewStatsByProductId | None = None) -> ProductRead:
    payload = ProductRead.model_validate(product)
    rating_avg, rating_count = _get_review_stats(product.id, review_stats_by_product_id)
    return payload.model_copy(update={"image_url": build_product_image_url(request, product), "rating_avg": rating_avg, "rating_count": rating_count})


def serialize_product_with_variants(
    request: Request,
    product: Product,
    *,
    review_stats_by_product_id: ReviewStatsByProductId | None = None,
    include_archived_variants: bool = False,
) -> ProductWithVariantsRead:
    payload = ProductWithVariantsRead.model_validate(product)
    visible_variants = [
        variant
        for variant in product.variants
        if include_archived_variants or not variant.archived
    ]
    variants = [serialize_product_variant(request, variant) for variant in visible_variants]
    rating_avg, rating_count = _get_review_stats(product.id, review_stats_by_product_id)
    return payload.model_copy(update={"image_url": build_product_image_url(request, product), "variants": variants, "rating_avg": rating_avg, "rating_count": rating_count})


def serialize_products(request: Request, products: list[Product], *, review_stats_by_product_id: ReviewStatsByProductId | None = None) -> list[ProductRead]:  return [serialize_product(request, product, review_stats_by_product_id=review_stats_by_product_id) for product in products]
def serialize_products_with_variants(
    request: Request,
    products: list[Product],
    *,
    review_stats_by_product_id: ReviewStatsByProductId | None = None,
    include_archived_variants: bool = False,
) -> list[ProductWithVariantsRead]:
    return [
        serialize_product_with_variants(
            request,
            product,
            review_stats_by_product_id=review_stats_by_product_id,
            include_archived_variants=include_archived_variants,
        )
        for product in products
    ]


def serialize_review(request: Request, review: Review) -> ReviewRead:
    attachments = [ReviewAttachmentRead(id=attachment.id, image_url=build_review_attachment_url(request, build_review_attachment_path(attachment.review_id, attachment.filename)), created_at=attachment.created_at, updated_at=attachment.updated_at) for attachment in review.attachments]
    return ReviewRead(id=review.id, author_username=PLACEHOLDER_SITE_REVIEW_AUTHOR if review.user_id == 0 else review.user.username, product_id=review.product_id, value=review.value, text=review.text, answer=review.answer, attachments=attachments, likes=review.likes, dislikes=review.dislikes, moderated=review.moderated, created_at=review.created_at, updated_at=review.updated_at)


def serialize_reviews(request: Request, reviews: list[Review]) -> list[ReviewRead]:
    return [serialize_review(request, review) for review in reviews]
