from datetime import datetime
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status
from src.app.services.catalog_merchandising import catalog_unit_price
from src.app.services.stock_visibility import get_stock_visibility_policy
from src.database.crud import create_order_draft, get_order_by_id, get_order_draft_by_id, get_orders_for_user as get_orders_for_user_crud
from src.database.models import Order, OrderDraft, OrderDraftItem, Product, ProductByCategory, Variant
from src.database.models.orders.history import OrderHistoryBucket, OrderStatusCode, get_order_history_bucket
from src.database.schemas import OrderDraftCreate


async def get_order_for_user(session: AsyncSession, *, user_id: int, order_id: int) -> Order | None: return await get_order_by_id(session, order_id, user_id=user_id)


async def get_orders_history_for_user(session: AsyncSession, *, user_id: int, history_bucket: OrderHistoryBucket | None = None, status_code: OrderStatusCode | None = None, created_from: datetime | None = None, created_to: datetime | None = None, limit: int = 20, offset: int = 0) -> list[Order]: return await get_orders_for_user_crud(session, user_id, history_bucket=history_bucket, status_code=status_code, created_from=created_from, created_to=created_to, limit=limit, offset=offset)


async def _get_locked_variants_for_repeat(session: AsyncSession, variant_ids: list[int]) -> dict[int, Variant]:
    if not variant_ids: return {}

    stmt = (select(Variant).options(selectinload(Variant.product).selectinload(Product.products_by_category).selectinload(ProductByCategory.category),).where(Variant.id.in_(variant_ids)).with_for_update())
    variants = list((await session.execute(stmt)).scalars().all())
    return {variant.id: variant for variant in variants}


async def repeat_order_as_draft_for_user(session: AsyncSession, *, user_id: int, order_id: int) -> OrderDraft | None:
    order = await get_order_by_id(session, order_id, user_id=user_id)
    if order is None: return None
    if get_order_history_bucket(order) != "completed": raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Повторить можно только завершенный заказ")
    if not order.items: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order is empty")

    variants_by_id = await _get_locked_variants_for_repeat(session, [item.variant_id for item in order.items])
    stock_policy = await get_stock_visibility_policy(session)
    draft_items: list[OrderDraftItem] = []
    basket_subtotal = Decimal("0.00")
    total_quantity = 0

    for order_item in order.items:
        variant = variants_by_id.get(order_item.variant_id)
        if variant is None or variant.product is None: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order contains unavailable items")
        visible_stock = stock_policy.visible_stock(variant.stock, variant.product)
        if variant.archived or visible_stock <= 0 or order_item.quantity > visible_stock: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order contains unavailable items")

        unit_price = catalog_unit_price(variant.price, variant.product)
        line_total = unit_price * order_item.quantity
        basket_subtotal += line_total
        total_quantity += order_item.quantity
        draft_items.append(OrderDraftItem(user_id=user_id, draft_id=0, product_id=variant.product_id, variant_id=variant.id, product_name=variant.product.name, product_sku=variant.product.sku, variant_name=variant.name, variant_sku=variant.sku, quantity=order_item.quantity, unit_price=unit_price, line_total=line_total,))

    draft = await create_order_draft(session, OrderDraftCreate(user_id=user_id, delivery_address_id=order.delivery_address_id, recipient_id=order.recipient_id, status="draft", items_count=len(draft_items), total_quantity=total_quantity, basket_subtotal=basket_subtotal, delivery_total=order.delivery_total, grand_total=basket_subtotal + order.delivery_total, currency=order.currency, delivery_period_min=order.delivery_period_min, delivery_period_max=order.delivery_period_max, draft_name=f"Повтор заказа №{order.order_number}", comment=order.comment,), commit=False,)

    for draft_item in draft_items: draft_item.draft_id = draft.id
    session.add_all(draft_items)
    await session.flush()
    await session.commit()
    created_draft = await get_order_draft_by_id(session, draft.id, user_id=user_id)
    if created_draft is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load repeated order draft")
    return created_draft
