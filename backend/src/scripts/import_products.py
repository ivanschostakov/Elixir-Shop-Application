import asyncio
import random
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.database import SessionLocal
from src.database.models import Product
from src.database.product_text import normalize_product_text
from src.normalize import optional_str
from src.product_media import resolve_product_image_path

CSV_PATH = "products_export_cleaned.csv"


def random_priority() -> int:
    return random.choices(population=[1, 2, 3, 4, 5], weights=[35, 30, 20, 10, 5], k=1)[0]


def priority_for_product(*, product_id: int | None, system_id) -> int:
    return random_priority() if resolve_product_image_path(product_id=product_id, system_id=system_id) is not None else 0


async def import_products():
    df = pd.read_csv(CSV_PATH)

    async with SessionLocal() as session:
        for _, row in df.iterrows():
            system_id = optional_str(row["system_id"])
            product = Product(
                system_id=system_id,
                sku=optional_str(row["sku"]),
                name=optional_str(row["name"]),
                description=normalize_product_text(optional_str(row["description"])),
                usage=normalize_product_text(optional_str(row["usage"])),
                expiration=normalize_product_text(optional_str(row["expiration"])),
                priority=0,
            )
            session.add(product)
            await session.flush()
            product.priority = priority_for_product(product_id=product.id, system_id=system_id)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(import_products())
