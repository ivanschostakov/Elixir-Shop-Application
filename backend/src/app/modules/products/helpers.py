from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from config import REVIEWS_MEDIA_DIR
from src.app.services.discounts import product_is_discountable
from src.app.services.catalog_merchandising import (
    CatalogMerchandisingPolicy,
    apply_percent_discount,
    product_catalog_discount_percent,
    product_is_new,
)
from src.app.services.referrals.calculations import quantize_money, quantize_percent
from src.app.services.referrals.profile import get_referral_profile_by_user_id, user_has_promo_code
from src.app.services.review_attachments import build_review_attachment_url
from src.app.services.stock_visibility import StockVisibilityPolicy
from src.database.models import Product, ProductQuestion, Review
from src.database.models.auth.user import User
from src.database.schemas import (
    ProductQuestionRead,
    ProductRead,
    ProductVariantRead,
    ProductWithVariantsRead,
    ReviewAttachmentRead,
    ReviewRead,
)
from src.product_media import build_products_media_url

ReviewStatsByProductId = dict[int, tuple[float, int]]
PLACEHOLDER_SITE_REVIEW_AUTHOR = "С сайта"


@dataclass(frozen=True, slots=True)
class ProductPriceDiscountContext:
    app_referral_percent: Decimal = Decimal("0.00")


NO_PRODUCT_PRICE_DISCOUNT_CONTEXT = ProductPriceDiscountContext()
DEFAULT_CATALOG_MERCHANDISING_POLICY = CatalogMerchandisingPolicy()


def product_image_url(request: Request, product: Product) -> str: return build_products_media_url(str(request.base_url), product.image_path)
def variant_image_url(request: Request, variant) -> str: return build_products_media_url(str(request.base_url), variant.image_path)
def review_attachment_path(review_id: int, filename: str) -> Path: return REVIEWS_MEDIA_DIR / str(review_id) / filename
def review_stats(product_id: int, stats: ReviewStatsByProductId | None) -> tuple[float, int]: return stats.get(product_id, (0.0, 0)) if stats else (0.0, 0)


async def get_user_product_discount_percent(db: AsyncSession, user: User | None) -> Decimal:
    if user is None: return Decimal("0.00")
    if not user_has_promo_code(user): return Decimal("0.00")
    profile = await get_referral_profile_by_user_id(db, user.id)
    if profile is None: return Decimal("0.00")
    return quantize_percent(profile.current_discount_percent)


async def get_user_product_price_discount_context(db: AsyncSession, user: User | None) -> ProductPriceDiscountContext:
    if user is None: return NO_PRODUCT_PRICE_DISCOUNT_CONTEXT
    app_percent = await get_user_product_discount_percent(db, user)
    return ProductPriceDiscountContext(app_referral_percent=app_percent)


def discounted_price(price: Decimal, percent: Decimal) -> Decimal:
    price, percent = quantize_money(price), quantize_percent(percent)
    if percent <= Decimal("0.00"): return price
    return max(Decimal("0.00"), quantize_money(price - ((price * percent) / Decimal("100.00"))))


def effective_discount_percent(original: Decimal, discounted: Decimal) -> Decimal:
    if original <= Decimal("0.00") or discounted >= original: return Decimal("0.00")
    return quantize_percent(((original - discounted) * Decimal("100.00")) / original)


def resolve_variant_price(
    price: Decimal,
    ctx: ProductPriceDiscountContext,
    *,
    product: Product | None = None,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    original = quantize_money(price)
    catalog_percent = product_catalog_discount_percent(product)
    personal_percent = ctx.app_referral_percent if product_is_discountable(product) else Decimal("0.00")
    combined_percent = min(
        Decimal("100.00"),
        quantize_percent(catalog_percent + personal_percent),
    )
    discounted = apply_percent_discount(original, combined_percent)
    return (
        original,
        discounted,
        combined_percent,
        catalog_percent,
        personal_percent,
    )


def serialize_product_variant(
    request: Request,
    variant,
    *,
    product: Product | None = None,
    discount_context: ProductPriceDiscountContext = NO_PRODUCT_PRICE_DISCOUNT_CONTEXT,
    stock_policy: StockVisibilityPolicy | None = None,
) -> ProductVariantRead:
    resolved_product = product or getattr(variant, "product", None)
    original, discounted, percent, catalog_percent, personal_percent = resolve_variant_price(
        variant.price,
        discount_context,
        product=resolved_product,
    )
    policy = stock_policy or StockVisibilityPolicy()
    return ProductVariantRead.model_validate(variant).model_copy(update={
        "image_url": variant_image_url(request, variant),
        "stock": policy.visible_stock(variant.stock, resolved_product),
        "original_price": original,
        "discounted_price": discounted,
        "discount_percent": percent,
        "catalog_discount_percent": catalog_percent,
        "personal_discount_percent": personal_percent,
    })


def serialize_product(
    request: Request,
    product: Product,
    *,
    review_stats_by_product_id: ReviewStatsByProductId | None = None,
    merchandising_policy: CatalogMerchandisingPolicy = DEFAULT_CATALOG_MERCHANDISING_POLICY,
) -> ProductRead:
    avg, count = review_stats(product.id, review_stats_by_product_id)
    return ProductRead.model_validate(product).model_copy(update={
        "image_url": product_image_url(request, product),
        "rating_avg": avg,
        "rating_count": count,
        "is_new": product_is_new(product, merchandising_policy),
        "catalog_discount_percent": product_catalog_discount_percent(product),
    })


def serialize_product_with_variants(
    request: Request,
    product: Product,
    *,
    review_stats_by_product_id: ReviewStatsByProductId | None = None,
    include_archived_variants: bool = False,
    discount_context: ProductPriceDiscountContext = NO_PRODUCT_PRICE_DISCOUNT_CONTEXT,
    stock_policy: StockVisibilityPolicy | None = None,
    merchandising_policy: CatalogMerchandisingPolicy = DEFAULT_CATALOG_MERCHANDISING_POLICY,
) -> ProductWithVariantsRead:
    avg, count = review_stats(product.id, review_stats_by_product_id)
    policy = stock_policy or StockVisibilityPolicy()
    variants = [
        serialize_product_variant(
            request,
            variant,
            product=product,
            discount_context=discount_context,
            stock_policy=policy,
        )
        for variant in product.variants
        if include_archived_variants or not variant.archived
    ]
    return ProductWithVariantsRead.model_validate(product).model_copy(update={
        "image_url": product_image_url(request, product),
        "variants": variants,
        "in_stock": any(
            not variant.archived
            and policy.visible_stock(variant.stock, product) > 0
            for variant in product.variants
        ),
        "rating_avg": avg,
        "rating_count": count,
        "is_new": product_is_new(product, merchandising_policy),
        "catalog_discount_percent": product_catalog_discount_percent(product),
    })


def serialize_products(
    request: Request,
    products: list[Product],
    *,
    review_stats_by_product_id: ReviewStatsByProductId | None = None,
    merchandising_policy: CatalogMerchandisingPolicy = DEFAULT_CATALOG_MERCHANDISING_POLICY,
) -> list[ProductRead]:
    return [
        serialize_product(
            request,
            product,
            review_stats_by_product_id=review_stats_by_product_id,
            merchandising_policy=merchandising_policy,
        )
        for product in products
    ]


def serialize_products_with_variants(
    request: Request,
    products: list[Product],
    *,
    review_stats_by_product_id: ReviewStatsByProductId | None = None,
    include_archived_variants: bool = False,
    discount_context: ProductPriceDiscountContext = NO_PRODUCT_PRICE_DISCOUNT_CONTEXT,
    stock_policy: StockVisibilityPolicy | None = None,
    merchandising_policy: CatalogMerchandisingPolicy = DEFAULT_CATALOG_MERCHANDISING_POLICY,
) -> list[ProductWithVariantsRead]:
    return [serialize_product_with_variants(
        request,
        product,
        review_stats_by_product_id=review_stats_by_product_id,
        include_archived_variants=include_archived_variants,
        discount_context=discount_context,
        stock_policy=stock_policy,
        merchandising_policy=merchandising_policy,
    ) for product in products]


def serialize_review(request: Request, review: Review) -> ReviewRead:
    attachments = [ReviewAttachmentRead(
        id=attachment.id,
        image_url=build_review_attachment_url(request, review_attachment_path(attachment.review_id, attachment.filename)),
        created_at=attachment.created_at,
        updated_at=attachment.updated_at,
    ) for attachment in review.attachments if getattr(attachment, "moderation_status", "approved") == "approved"]
    author_label = PLACEHOLDER_SITE_REVIEW_AUTHOR
    if review.hide_sender_name:
        author_label = "Анонимный покупатель"
    elif review.user is not None:
        author_label = (review.user.name or review.user.phone_number or review.user.email or PLACEHOLDER_SITE_REVIEW_AUTHOR).strip()
    elif review.guest_name:
        author_label = review.guest_name.strip()

    return ReviewRead(
        id=review.id,
        author_username=author_label or PLACEHOLDER_SITE_REVIEW_AUTHOR,
        is_anonymous=review.hide_sender_name,
        product_id=review.product_id,
        value=review.value,
        text=review.text,
        answer=review.answer,
        attachments=attachments,
        likes=review.likes,
        dislikes=review.dislikes,
        moderated=review.moderated,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def serialize_reviews(request: Request, reviews: list[Review]) -> list[ReviewRead]:
    return [serialize_review(request, review) for review in reviews]


def serialize_product_question(question: ProductQuestion) -> ProductQuestionRead:
    author_label = "Гость"
    if question.user is not None:
        author_label = (
            question.user.name
            or question.user.phone_number
            or question.user.email
            or author_label
        ).strip()
    elif question.guest_name:
        author_label = question.guest_name.strip()

    return ProductQuestionRead(
        id=question.id,
        author_username=author_label or "Гость",
        product_id=question.product_id,
        text=question.text,
        answer=question.answer,
        created_at=question.created_at,
        updated_at=question.updated_at,
    )


def serialize_product_questions(
    questions: list[ProductQuestion],
) -> list[ProductQuestionRead]:
    return [serialize_product_question(question) for question in questions]
