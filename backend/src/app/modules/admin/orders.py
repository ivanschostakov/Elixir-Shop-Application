from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.app.modules.admin.helpers import ensure_not_stale, serialize_admin_order, serialize_admin_order_detail
from src.app.modules.admin.schemas import AdminOrderDetail, AdminOrderListItem, AdminOrderTransitionPayload, AdminPage
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.app.services.orders import apply_amocrm_status_update
from src.database import get_db
from src.database.models import Order, User
from src.database.models.orders.history import OrderStatusCode, build_status_code_clause, get_order_status_code
from src.integrations.amocrm import get_amocrm_client
from src.integrations.amocrm.constants import STATUS_IDS

admin_orders_router = APIRouter(prefix="/orders", tags=["admin_orders"])
amocrm_client = get_amocrm_client()

STATUS_ID_BY_CODE: dict[OrderStatusCode, int] = {
    "created": STATUS_IDS["main"],
    "invoice_sent": STATUS_IDS["pending_payment"],
    "paid": STATUS_IDS["check_paid"],
    "waiting_response": STATUS_IDS["waiting_response"],
    "packaged": STATUS_IDS["packaged"],
    "sent": STATUS_IDS["package_sent"],
    "delivered": STATUS_IDS["package_delivered"],
    "canceled": STATUS_IDS["canceled"],
    "completed": STATUS_IDS["won"],
    "refund_declined": STATUS_IDS["refund_declined"],
}

ALLOWED_TRANSITIONS: dict[OrderStatusCode, frozenset[OrderStatusCode]] = {
    "created": frozenset(("invoice_sent", "waiting_response", "canceled")),
    "invoice_sent": frozenset(("paid", "waiting_response", "canceled")),
    "paid": frozenset(("waiting_response", "packaged", "refund_declined")),
    "waiting_response": frozenset(("paid", "packaged", "canceled")),
    "packaged": frozenset(("sent", "canceled", "refund_declined")),
    "sent": frozenset(("delivered", "refund_declined")),
    "delivered": frozenset(("completed", "refund_declined")),
    "canceled": frozenset(),
    "completed": frozenset(("refund_declined",)),
    "refund_declined": frozenset(),
}


def _order_options():
    return (
        selectinload(Order.user),
        selectinload(Order.items),
        selectinload(Order.recipient),
        selectinload(Order.delivery_address),
    )


async def _get_order(db: AsyncSession, order_id: int) -> Order:
    order = (await db.execute(select(Order).options(*_order_options()).where(Order.id == order_id).execution_options(populate_existing=True))).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@admin_orders_router.get("", response_model=AdminPage[AdminOrderListItem])
async def list_orders(
    q: str | None = Query(default=None, max_length=100),
    status_code: OrderStatusCode | None = None,
    payment_status: str | None = Query(default=None, max_length=32),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("orders.read")),
) -> AdminPage[AdminOrderListItem]:
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(
            Order.order_code.ilike(pattern),
            Order.payment_invoice_id.ilike(pattern),
            User.email.ilike(pattern),
            User.phone_number.ilike(pattern),
            User.name.ilike(pattern),
            User.surname.ilike(pattern),
        ))
    if status_code:
        filters.append(build_status_code_clause(Order, status_code))
    if payment_status:
        filters.append(Order.payment_status == payment_status)
    if created_from:
        filters.append(Order.created_at >= created_from)
    if created_to:
        filters.append(Order.created_at <= created_to)

    base = select(Order).join(User, User.id == Order.user_id).where(*filters)
    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = list((await db.execute(base.options(*_order_options()).order_by(Order.created_at.desc(), Order.id.desc()).offset(offset).limit(limit))).scalars().unique().all())
    return AdminPage(items=[serialize_admin_order(row) for row in rows], total=total, limit=limit, offset=offset)


@admin_orders_router.get("/{order_id}", response_model=AdminOrderDetail)
async def get_order_detail(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("orders.read")),
) -> AdminOrderDetail:
    return serialize_admin_order_detail(await _get_order(db, order_id))


@admin_orders_router.post("/{order_id}/transition", response_model=AdminOrderDetail)
async def transition_order(
    order_id: int,
    payload: AdminOrderTransitionPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("orders.transition", write=True)),
) -> AdminOrderDetail:
    order = await _get_order(db, order_id)
    ensure_not_stale(actual=order.updated_at, expected=payload.expected_updated_at)
    current_code = get_order_status_code(order)
    if current_code == payload.status_code:
        return serialize_admin_order_detail(order)
    if payload.status_code not in ALLOWED_TRANSITIONS[current_code]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_transition", "from": current_code, "to": payload.status_code},
        )
    if not order.amocrm_lead_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order is not linked to amoCRM")

    before = serialize_admin_order_detail(order).model_dump(mode="json")
    target_status_id = STATUS_ID_BY_CODE[payload.status_code]
    try:
        await amocrm_client.update_lead_status(int(order.amocrm_lead_id), target_status_id)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="amoCRM status update failed") from error

    order = await apply_amocrm_status_update(db, order=order, status_id=target_status_id)
    order = await _get_order(db, order.id)
    after = serialize_admin_order_detail(order)
    await add_admin_audit(
        db,
        request,
        context,
        action="order.transition",
        entity_type="order",
        entity_id=order.id,
        before=before,
        after=after.model_dump(mode="json"),
        details={"from_status_code": current_code, "to_status_code": payload.status_code},
    )
    await db.commit()
    return after
