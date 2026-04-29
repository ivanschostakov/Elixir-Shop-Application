from pathlib import Path

from config import PRODUCTS_MEDIA_DIR, PUBLIC_API_BASE_URL
from src.normalize import optional_str

PRODUCT_IMAGE_PLACEHOLDER = "product.png"


def product_media_dir(product_id: int | None) -> Path | None:
    if product_id is None:
        return None
    return PRODUCTS_MEDIA_DIR / str(product_id)


def product_image_path(product_id: int | None, system_id) -> Path | None:
    system_id_str = optional_str(system_id)
    directory = product_media_dir(product_id)
    if directory is None or system_id_str is None:
        return None
    return directory / f"{system_id_str}.png"


def variant_image_path(product_id: int | None, system_id) -> Path | None:
    return product_image_path(product_id, system_id)


def resolve_product_image_path(*, product_id: int | None, system_id) -> Path | None:
    current_path = product_image_path(product_id, system_id)
    if current_path is not None and current_path.exists():
        return current_path

    return None


def resolve_variant_image_path(*, product_id: int | None, system_id) -> Path | None:
    current_path = variant_image_path(product_id, system_id)
    if current_path is not None and current_path.exists():
        return current_path

    return None


def products_media_relative_path(image_path: Path) -> str:
    try:
        return image_path.relative_to(PRODUCTS_MEDIA_DIR).as_posix()
    except ValueError:
        return image_path.name


def build_products_media_url(base_url: str, image_path: Path | None) -> str:
    base = (PUBLIC_API_BASE_URL or base_url).rstrip("/")
    if image_path is None or not image_path.exists():
        return f"{base}/media/products/{PRODUCT_IMAGE_PLACEHOLDER}"

    version = int(image_path.stat().st_mtime_ns)
    relative_path = products_media_relative_path(image_path)
    return f"{base}/media/products/{relative_path}?v={version}"
