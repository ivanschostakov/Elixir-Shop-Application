from fastapi import APIRouter, Depends, HTTPException, Query, Request
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas import CreatePaymentPayload, PaymentStatusRead
from src.app.services.app_integrity import require_app_integrity
from src.app.services.orders import create_payment_for_order, get_order_for_user, get_payment_status_for_order
from src.app.services.customer_intelligence import record_customer_event_safe
from src.database import get_db
from src.database.models import User

payments_router = APIRouter(prefix="/payments", tags=["payments"])


@payments_router.post("/create", response_model=PaymentStatusRead)
async def create_payment(payload: CreatePaymentPayload, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user), _app_integrity: None = Depends(require_app_integrity("payments:create"))) -> PaymentStatusRead:
    order = await get_order_for_user(db, user_id=current_user.id, order_id=payload.order_id)
    if order is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    result = await create_payment_for_order(
        db,
        request=request,
        order=order,
        payment_method=payload.payment_method,
    )
    if result.get("is_paid"):
        await record_customer_event_safe(
            db,
            user_id=current_user.id,
            event_name="order_paid",
            event_id=uuid.uuid5(uuid.NAMESPACE_URL, f"elixir-shop:user:{current_user.id}:order:{order.id}:paid"),
            entity_type="order",
            entity_id=order.id,
            properties={"order_code": order.order_code, "payment_method": result.get("payment_method")},
            commit=True,
        )
    return PaymentStatusRead.model_validate(result)


@payments_router.get("/status", response_model=PaymentStatusRead)
async def get_payment_status(request: Request, order_id: int = Query(..., ge=1), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user), _app_integrity: None = Depends(require_app_integrity("payments:status"))) -> PaymentStatusRead:
    order = await get_order_for_user(db, user_id=current_user.id, order_id=order_id)
    if order is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    result = await get_payment_status_for_order(db, request=request, order=order)
    if result.get("is_paid"):
        await record_customer_event_safe(
            db,
            user_id=current_user.id,
            event_name="order_paid",
            event_id=uuid.uuid5(uuid.NAMESPACE_URL, f"elixir-shop:user:{current_user.id}:order:{order.id}:paid"),
            entity_type="order",
            entity_id=order.id,
            properties={"order_code": order.order_code, "payment_method": result.get("payment_method")},
            commit=True,
        )
    return PaymentStatusRead.model_validate(result)
