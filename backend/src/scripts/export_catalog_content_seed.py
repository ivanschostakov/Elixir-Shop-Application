import asyncio
import json

from sqlalchemy import select

from src.database import SessionLocal, engine
from src.database.models import Product


async def export_catalog_content_seed() -> None:
    async with SessionLocal() as session:
        products = list((
            await session.execute(
                select(Product).order_by(Product.id.asc())
            )
        ).scalars().all())
    print(json.dumps(
        {
            "products": [
                {
                    "system_id": str(product.system_id),
                    "sku": product.sku,
                    "name": product.name,
                    "description": product.description,
                    "usage": product.usage,
                    "storage": product.expiration,
                }
                for product in products
                if product.system_id is not None
            ]
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(export_catalog_content_seed())
