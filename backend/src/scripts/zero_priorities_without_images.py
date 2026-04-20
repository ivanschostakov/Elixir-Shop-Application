import asyncio
from datetime import timedelta

from sqlalchemy import func, select

from src.database import SessionLocal
from src.database.models import Product


async def zero_priorities_without_images() -> None:
    async with SessionLocal() as session:
        oldest_created_at = await session.scalar(select(func.min(Product.created_at)))
        if oldest_created_at is None:
            print("No products found.")
            return

        demoted_created_at = oldest_created_at - timedelta(seconds=1)
        products = list((await session.execute(select(Product))).scalars().all())

        updated_count = 0
        for product in products:
            if product.has_image:
                continue
            product.priority = 0
            if product.created_at > demoted_created_at:
                product.created_at = demoted_created_at
            updated_count += 1

        await session.commit()
        print(f"Updated {updated_count} products without images.")


if __name__ == "__main__":
    asyncio.run(zero_priorities_without_images())
