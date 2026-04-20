from fastapi import Request

from src.database.models import Product
from src.database.schemas import ProductRead, ProductVariantRead, ProductWithVariantsRead
from src.product_media import build_products_media_url


def build_product_image_url(request: Request, product: Product) -> str:
    return build_products_media_url(str(request.base_url), product.image_path)


def build_variant_image_url(request: Request, variant) -> str:
    return build_products_media_url(str(request.base_url), variant.image_path)


def serialize_product_variant(request: Request, variant) -> ProductVariantRead:
    payload = ProductVariantRead.model_validate(variant)
    return payload.model_copy(update={"image_url": build_variant_image_url(request, variant)})


def serialize_product(request: Request, product: Product) -> ProductRead:
    payload = ProductRead.model_validate(product)
    return payload.model_copy(update={"image_url": build_product_image_url(request, product)})


def serialize_product_with_variants(request: Request, product: Product) -> ProductWithVariantsRead:
    payload = ProductWithVariantsRead.model_validate(product)
    variants = [serialize_product_variant(request, variant) for variant in product.variants]
    return payload.model_copy(update={"image_url": build_product_image_url(request, product), "variants": variants})


def serialize_products(request: Request, products: list[Product]) -> list[ProductRead]:
    return [serialize_product(request, product) for product in products]


def serialize_products_with_variants(request: Request, products: list[Product]) -> list[ProductWithVariantsRead]:
    return [serialize_product_with_variants(request, product) for product in products]
