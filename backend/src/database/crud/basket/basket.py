from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import Basket, BasketItem, Product, ProductByCategory
from src.database.schemas import BasketCreate, BasketUpdate


def _basket_load_options():
    return (
        selectinload(Basket.delivery_address),
        selectinload(Basket.recipient),
        selectinload(Basket.items).selectinload(BasketItem.product),
        selectinload(Basket.items).selectinload(BasketItem.product).selectinload(Product.products_by_category).selectinload(ProductByCategory.category),
        selectinload(Basket.items).selectinload(BasketItem.variant),
    )


async def create_basket(session: AsyncSession, data: BasketCreate) -> Basket:
    basket = Basket(**data.model_dump())
    session.add(basket)
    await session.commit()
    await session.refresh(basket)
    return basket


async def get_basket_by_id(session: AsyncSession, basket_id: int) -> Basket | None:
    stmt = select(Basket).options(*_basket_load_options()).where(Basket.id == basket_id).execution_options(populate_existing=True)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_basket_by_user_id(session: AsyncSession, user_id: int) -> Basket | None:
    stmt = select(Basket).options(*_basket_load_options()).where(Basket.user_id == user_id).execution_options(populate_existing=True)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_baskets(session: AsyncSession, *, user_id: int | None = None, offset: int = 0, limit: int = 100) -> list[Basket]:
    stmt = select(Basket)

    if user_id is not None: stmt = stmt.where(Basket.user_id == user_id)
    stmt = stmt.order_by(Basket.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_basket(session: AsyncSession, basket: Basket, data: BasketUpdate) -> Basket:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(basket, field, value)
    await session.commit()
    await session.refresh(basket)
    return basket


async def clear_basket(session: AsyncSession, basket_id: int) -> Basket | None:
    basket = await get_basket_by_id(session, basket_id)
    if basket is None: return None

    await session.execute(delete(BasketItem).where(BasketItem.basket_id == basket_id))
    await session.commit()
    return await get_basket_by_id(session, basket_id)


async def delete_basket(session: AsyncSession, basket: Basket) -> None:
    await session.delete(basket)
    await session.commit()
