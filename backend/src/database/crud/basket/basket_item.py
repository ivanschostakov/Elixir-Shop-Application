from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now

from src.database.models import BasketItem


async def create_basket_item(session: AsyncSession, *, basket_id: int, user_id: int, product_id: int, variant_id: int, quantity: int, price: Decimal, commit: bool = True) -> BasketItem:
    timestamp = ufa_now()
    table = BasketItem.__table__
    insert_stmt = pg_insert(table).values(
        basket_id=basket_id,
        user_id=user_id,
        product_id=product_id,
        dose_id=variant_id,
        quantity=quantity,
        price=price,
        created_at=timestamp,
        updated_at=timestamp,
    )
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=[table.c.basket_id, table.c.dose_id],
        set_={
            "user_id": user_id,
            "product_id": product_id,
            "quantity": table.c.quantity + insert_stmt.excluded.quantity,
            "price": price,
            "updated_at": timestamp,
        },
    ).returning(table.c.id)

    basket_item_id = (await session.execute(stmt)).scalar_one()
    if commit:
        await session.commit()
    else:
        await session.flush()
    return await get_basket_item_by_id(session, basket_item_id)


async def get_basket_item_by_id(session: AsyncSession, basket_item_id: int, *, basket_id: int | None = None, user_id: int | None = None) -> BasketItem | None:
    stmt = select(BasketItem).where(BasketItem.id == basket_item_id)
    if basket_id is not None: stmt = stmt.where(BasketItem.basket_id == basket_id)
    if user_id is not None: stmt = stmt.where(BasketItem.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_basket_item_by_basket_and_variant(session: AsyncSession, basket_id: int, variant_id: int, *, user_id: int | None = None) -> BasketItem | None:
    stmt = select(BasketItem).where(BasketItem.basket_id == basket_id, BasketItem.variant_id == variant_id)
    if user_id is not None: stmt = stmt.where(BasketItem.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_basket_items(session: AsyncSession, *, user_id: int | None = None, basket_id: int | None = None, product_id: int | None = None, variant_id: int | None = None, offset: int = 0, limit: int = 100) -> list[BasketItem]:
    stmt = select(BasketItem)
    if user_id is not None: stmt = stmt.where(BasketItem.user_id == user_id)
    if basket_id is not None: stmt = stmt.where(BasketItem.basket_id == basket_id)
    if product_id is not None: stmt = stmt.where(BasketItem.product_id == product_id)
    if variant_id is not None: stmt = stmt.where(BasketItem.variant_id == variant_id)
    stmt = stmt.order_by(BasketItem.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_basket_item(session: AsyncSession, basket_item: BasketItem, *, basket_id: int, user_id: int, product_id: int, quantity: int, price: Decimal) -> BasketItem:
    basket_item.basket_id = basket_id
    basket_item.user_id = user_id
    basket_item.product_id = product_id
    basket_item.quantity = quantity
    basket_item.price = price
    await session.commit()
    await session.refresh(basket_item)
    return basket_item


async def delete_basket_item(session: AsyncSession, basket_item: BasketItem) -> None:
    await session.delete(basket_item)
    await session.commit()
