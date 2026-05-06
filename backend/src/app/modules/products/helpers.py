from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from fastapi import Request

from config import REVIEWS_MEDIA_DIR, ufa_now
from src.app.services.benefits.options import best_option_key
from src.app.services.benefits.website import build_website_entitlement_option
from src.app.services.referrals.calculations import calculate_personal_discount_percent, quantize_money, quantize_percent
from src.app.services.referrals.service import get_referral_profile_by_user_id, profile_has_referral_participation
from src.app.services.review_attachments import build_review_attachment_url
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import Product, Review, WebsiteIdentity
from src.database.models.auth.user import User
from src.database.schemas import ProductRead, ProductVariantRead, ProductWithVariantsRead, ReviewAttachmentRead, ReviewRead
from src.product_media import build_products_media_url

ReviewStatsByProductId = dict[int, tuple[float, int]]
PLACEHOLDER_SITE_REVIEW_AUTHOR = "С сайта"


@dataclass(frozen=True, slots=True)
class ProductPriceDiscountContext:
    app_referral_percent: Decimal = Decimal("0.00")
    website_discount_entitlements: tuple = ()


NO_PRODUCT_PRICE_DISCOUNT_CONTEXT = ProductPriceDiscountContext()


def build_product_image_url(request: Request, product: Product) -> str:
    return build_products_media_url(str(request.base_url), product.image_path)


def build_variant_image_url(request: Request, variant) -> str:
    return build_products_media_url(str(request.base_url), variant.image_path)


def build_review_attachment_path(review_id: int, filename: str) -> Path:
    return REVIEWS_MEDIA_DIR / str(review_id) / filename


async def get_user_product_discount_percent(db: AsyncSession, user: User | None) -> Decimal:
    if user is None:
        return Decimal("0.00")

    profile = await get_referral_profile_by_user_id(db, user.id)
    if profile is None:
        return Decimal("0.00")

    return calculate_personal_discount_percent(
        profile.referral_discount_base_total,
        has_referrer=profile_has_referral_participation(profile),
    )


async def get_user_product_price_discount_context(db: AsyncSession, user: User | None) -> ProductPriceDiscountContext:
    if user is None:
        return NO_PRODUCT_PRICE_DISCOUNT_CONTEXT

    app_referral_percent = await get_user_product_discount_percent(db, user)
    website_identity = (
        await db.execute(
            select(WebsiteIdentity)
            .options(selectinload(WebsiteIdentity.discount_entitlements))
            .where(WebsiteIdentity.user_id == user.id)
        )
    ).scalar_one_or_none()
    return ProductPriceDiscountContext(
        app_referral_percent=app_referral_percent,
        website_discount_entitlements=tuple(website_identity.discount_entitlements) if website_identity is not None else (),
    )


def _discounted_variant_price(price: Decimal, discount_percent: Decimal) -> Decimal:
    original_price = quantize_money(price)
    discount = quantize_percent(discount_percent)
    if discount <= Decimal("0.00"):
        return original_price
    discounted_price = original_price - ((original_price * discount) / Decimal("100.00"))
    return max(Decimal("0.00"), quantize_money(discounted_price))


def _effective_discount_percent(*, original_price: Decimal, discounted_price: Decimal) -> Decimal:
    if original_price <= Decimal("0.00") or discounted_price >= original_price:
        return Decimal("0.00")
    return quantize_percent(((original_price - discounted_price) * Decimal("100.00")) / original_price)


def _apply_website_discount_entitlement(price: Decimal, discount_context: ProductPriceDiscountContext) -> Decimal:
    if not discount_context.website_discount_entitlements:
        return price

    options = [
        build_website_entitlement_option(entitlement, subtotal=price, now=ufa_now())
        for entitlement in discount_context.website_discount_entitlements
    ]
    applicable_options = [option for option in options if option.is_applicable]
    applicable_options.sort(key=best_option_key, reverse=True)
    option = applicable_options[0] if applicable_options else None
    if option is None:
        return price

    if option.calculation_mode == "percent" and option.discount_percent is not None:
        return _discounted_variant_price(price, option.discount_percent)
    if option.calculation_mode == "fixed_amount" and option.discount_amount is not None:
        return max(Decimal("0.00"), quantize_money(price - min(price, quantize_money(option.discount_amount))))
    return price


def _resolve_variant_price_preview(
    price: Decimal,
    discount_context: ProductPriceDiscountContext,
) -> tuple[Decimal, Decimal, Decimal]:
    original_price = quantize_money(price)
    discounted_price = _discounted_variant_price(original_price, discount_context.app_referral_percent)
    discounted_price = _apply_website_discount_entitlement(discounted_price, discount_context)
    discounted_price = quantize_money(discounted_price)
    return (
        original_price,
        discounted_price,
        _effective_discount_percent(original_price=original_price, discounted_price=discounted_price),
    )


def serialize_product_variant(
    request: Request,
    variant,
    *,
    discount_context: ProductPriceDiscountContext = NO_PRODUCT_PRICE_DISCOUNT_CONTEXT,
) -> ProductVariantRead:
    payload = ProductVariantRead.model_validate(variant)
    original_price, discounted_price, discount_percent = _resolve_variant_price_preview(variant.price, discount_context)
    return payload.model_copy(
        update={
            "image_url": build_variant_image_url(request, variant),
            "original_price": original_price,
            "discounted_price": discounted_price,
            "discount_percent": discount_percent,
        }
    )


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
    discount_context: ProductPriceDiscountContext = NO_PRODUCT_PRICE_DISCOUNT_CONTEXT,
) -> ProductWithVariantsRead:
    payload = ProductWithVariantsRead.model_validate(product)
    visible_variants = [
        variant
        for variant in product.variants
        if include_archived_variants or not variant.archived
    ]
    variants = [serialize_product_variant(request, variant, discount_context=discount_context) for variant in visible_variants]
    rating_avg, rating_count = _get_review_stats(product.id, review_stats_by_product_id)
    return payload.model_copy(update={"image_url": build_product_image_url(request, product), "variants": variants, "rating_avg": rating_avg, "rating_count": rating_count})


def serialize_products(request: Request, products: list[Product], *, review_stats_by_product_id: ReviewStatsByProductId | None = None) -> list[ProductRead]:  return [serialize_product(request, product, review_stats_by_product_id=review_stats_by_product_id) for product in products]
def serialize_products_with_variants(
    request: Request,
    products: list[Product],
    *,
    review_stats_by_product_id: ReviewStatsByProductId | None = None,
    include_archived_variants: bool = False,
    discount_context: ProductPriceDiscountContext = NO_PRODUCT_PRICE_DISCOUNT_CONTEXT,
) -> list[ProductWithVariantsRead]:
    return [
        serialize_product_with_variants(
            request,
            product,
            review_stats_by_product_id=review_stats_by_product_id,
            include_archived_variants=include_archived_variants,
            discount_context=discount_context,
        )
        for product in products
    ]


def serialize_review(request: Request, review: Review) -> ReviewRead:
    attachments = [ReviewAttachmentRead(id=attachment.id, image_url=build_review_attachment_url(request, build_review_attachment_path(attachment.review_id, attachment.filename)), created_at=attachment.created_at, updated_at=attachment.updated_at) for attachment in review.attachments]
    return ReviewRead(id=review.id, author_username=PLACEHOLDER_SITE_REVIEW_AUTHOR if review.user_id == 0 else review.user.username, product_id=review.product_id, value=review.value, text=review.text, answer=review.answer, attachments=attachments, likes=review.likes, dislikes=review.dislikes, moderated=review.moderated, created_at=review.created_at, updated_at=review.updated_at)


def serialize_reviews(request: Request, reviews: list[Review]) -> list[ReviewRead]:
    return [serialize_review(request, review) for review in reviews]
