from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas import CreatePaymentPayload, PaymentStatusRead
from src.app.services.orders import create_payment_for_order, get_order_for_user, get_payment_status_for_order
from src.database import get_db
from src.database.models import User

payments_router = APIRouter(prefix="/payments", tags=["payments"])


@payments_router.post("/create", response_model=PaymentStatusRead)
async def create_payment(
    payload: CreatePaymentPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentStatusRead:
    order = await get_order_for_user(db, user_id=current_user.id, order_id=payload.order_id)
    if order is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return PaymentStatusRead.model_validate(await create_payment_for_order(db, request=request, order=order))


@payments_router.get("/status", response_model=PaymentStatusRead)
async def get_payment_status(
    request: Request,
    order_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentStatusRead:
    order = await get_order_for_user(db, user_id=current_user.id, order_id=order_id)
    if order is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return PaymentStatusRead.model_validate(await get_payment_status_for_order(db, request=request, order=order))
