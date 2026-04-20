import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import PRODUCTS_MEDIA_DIR
from src.database import SessionLocal
from src.database.models import Product, Variant
from src.product_media import product_image_path, variant_image_path


async def reorganize_product_images() -> None:
    async with SessionLocal() as session:
        products = list((await session.execute(select(Product.id, Product.system_id))).all())
        variants = list((await session.execute(select(Variant.product_id, Variant.system_id))).all())

    product_targets = {
        str(system_id): product_image_path(product_id, system_id) for product_id, system_id in products if system_id is not None
    }
    variant_targets = {
        str(system_id): variant_image_path(product_id, system_id) for product_id, system_id in variants if system_id is not None
    }

    moved_products = 0
    moved_variants = 0
    skipped_existing = 0
    unmatched_files: list[str] = []

    for source_path in sorted(PRODUCTS_MEDIA_DIR.glob("*.png")):
        if source_path.name == "product.png":
            continue

        target_path = product_targets.get(source_path.stem)
        target_kind = "product"
        if target_path is None:
            target_path = variant_targets.get(source_path.stem)
            target_kind = "variant"

        if target_path is None:
            unmatched_files.append(source_path.name)
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            skipped_existing += 1
            continue

        source_path.rename(target_path)
        if target_kind == "product":
            moved_products += 1
        else:
            moved_variants += 1

    print(f"moved_products={moved_products}")
    print(f"moved_variants={moved_variants}")
    print(f"skipped_existing={skipped_existing}")
    print(f"unmatched_files={len(unmatched_files)}")
    for file_name in unmatched_files[:20]:
        print(f"unmatched={file_name}")


if __name__ == "__main__":
    asyncio.run(reorganize_product_images())
