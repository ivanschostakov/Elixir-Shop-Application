import asyncio
import shutil
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

    copied_products = 0
    copied_variants = 0
    skipped_existing = 0
    unmatched_system_ids: list[str] = []

    source_paths_by_system_id: dict[str, Path] = {}
    for source_path in sorted(PRODUCTS_MEDIA_DIR.rglob("*.png")):
        if source_path.name == "product.png":
            continue
        source_paths_by_system_id.setdefault(source_path.stem, source_path)

    for system_id_str, target_path in product_targets.items():
        source_path = source_paths_by_system_id.get(system_id_str)
        if source_path is None:
            unmatched_system_ids.append(system_id_str)
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            skipped_existing += 1
            continue

        shutil.copy2(source_path, target_path)
        copied_products += 1

    for system_id_str, target_path in variant_targets.items():
        source_path = source_paths_by_system_id.get(system_id_str)
        if source_path is None:
            unmatched_system_ids.append(system_id_str)
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            skipped_existing += 1
            continue

        shutil.copy2(source_path, target_path)
        copied_variants += 1

    print(f"copied_products={copied_products}")
    print(f"copied_variants={copied_variants}")
    print(f"skipped_existing={skipped_existing}")
    unique_unmatched = sorted(set(unmatched_system_ids))
    print(f"unmatched_system_ids={len(unique_unmatched)}")
    for system_id_str in unique_unmatched[:20]:
        print(f"unmatched={system_id_str}")


if __name__ == "__main__":
    asyncio.run(reorganize_product_images())
