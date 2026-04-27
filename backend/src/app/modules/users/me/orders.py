from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas import CreateOrderPayload
from src.app.services.orders import (
    create_order_from_draft_for_user,
    get_order_for_user,
    get_orders_history_for_user,
    serialize_order,
    serialize_orders,
)
from src.database import get_db
from src.database.models import User
from src.database.models.orders.history import OrderHistoryBucket, OrderStatusCode
from src.database.schemas import OrderRead

my_orders_router = APIRouter(prefix="/orders", tags=["my_orders"])


@my_orders_router.post("", response_model=OrderRead)
async def create_my_order(
    payload: CreateOrderPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderRead:
    order = await create_order_from_draft_for_user(
        db,
        request=request,
        user=current_user,
        draft_id=payload.draft_id,
        payment_method=payload.payment_method,
    )
    return await serialize_order(request, db, order)


@my_orders_router.get("", response_model=list[OrderRead])
async def list_my_orders(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    history_bucket: OrderHistoryBucket | None = Query(default=None),
    status_code: OrderStatusCode | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OrderRead]:
    orders = await get_orders_history_for_user(
        db,
        user_id=current_user.id,
        history_bucket=history_bucket,
        status_code=status_code,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )
    return await serialize_orders(request, db, orders)


@my_orders_router.get("/{order_id}", response_model=OrderRead)
async def get_my_order(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderRead:
    order = await get_order_for_user(db, user_id=current_user.id, order_id=order_id)
    if order is None:
        from fastapi import HTTPException
        from starlette import status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return await serialize_order(request, db, order)
