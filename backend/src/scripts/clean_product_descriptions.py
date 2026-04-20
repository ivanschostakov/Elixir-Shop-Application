import asyncio

from sqlalchemy import select

from src.database import SessionLocal
from src.database.models import Product
from src.database.product_text import normalize_product_text


async def clean_product_descriptions() -> None:
    changed: list[tuple[int, str]] = []

    async with SessionLocal() as session:
        products = list((await session.execute(select(Product).order_by(Product.id))).scalars().all())

        for product in products:
            cleaned = normalize_product_text(product.description)
            if cleaned == product.description:
                continue
            product.description = cleaned
            changed.append((product.id, product.name))

        await session.commit()

    print(f"Updated {len(changed)} product descriptions.")
    for product_id, product_name in changed:
        print(f"{product_id}\t{product_name}")


if __name__ == "__main__":
    asyncio.run(clean_product_descriptions())
