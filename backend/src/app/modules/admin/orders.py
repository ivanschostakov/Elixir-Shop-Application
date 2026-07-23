from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.app.modules.admin.helpers import ensure_not_stale, serialize_admin_order, serialize_admin_order_detail
from config import (
    CDEK_ACCOUNT,
    CDEK_SECURE_PASSWORD,
    INTELLECTMONEY_BEARER_TOKEN,
    INTELLECTMONEY_SHOP_ID,
    MOY_SKLAD_TOKEN,
    YANDEX_DELIVERY_TOKEN,
)
from src.app.modules.admin.schemas import (
    AdminOrderDetail,
    AdminOrderListItem,
    AdminOrderOperationPayload,
    AdminOrderTransitionPayload,
    AdminPage,
    IntegrationRunRead,
)
from src.app.services.admin import (
    AdminContext,
    add_admin_audit,
    default_max_attempts,
    enqueue_integration_run,
    require_permission,
)
from src.app.services.admin.order_transitions import ALLOWED_TRANSITIONS, transition_is_allowed, transition_status_id
from src.database import get_db
from src.database.models import IntegrationRun, Order, User
from src.database.models.orders.history import OrderStatusCode, build_status_code_clause, get_order_status_code

admin_orders_router = APIRouter(prefix="/orders", tags=["admin_orders"])

AdminOrderOperation = Literal["payment_check", "moysklad_sync", "delivery_create"]


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


@admin_orders_router.get("/{order_id}/integration-runs", response_model=list[IntegrationRunRead])
async def get_order_integration_runs(
    order_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("orders.read")),
) -> list[IntegrationRunRead]:
    await _get_order(db, order_id)
    rows = list((await db.execute(
        select(IntegrationRun)
        .where(IntegrationRun.target_type == "order", IntegrationRun.target_id == str(order_id))
        .order_by(IntegrationRun.started_at.desc(), IntegrationRun.id.desc())
        .limit(limit)
    )).scalars().all())
    return [IntegrationRunRead.model_validate(row) for row in rows]


def _operation_provider(order: Order, operation: AdminOrderOperation) -> tuple[str, str]:
    if operation == "payment_check":
        if not (INTELLECTMONEY_BEARER_TOKEN and INTELLECTMONEY_SHOP_ID):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="IntellectMoney is not configured")
        return "intellectmoney", "payment_check"
    if operation == "moysklad_sync":
        if not MOY_SKLAD_TOKEN:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MoySklad is not configured")
        return "moysklad", "moysklad_order_sync"

    delivery_service = (order.selected_delivery_service or "").strip().upper()
    if delivery_service == "CDEK":
        if not (CDEK_ACCOUNT and CDEK_SECURE_PASSWORD):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CDEK is not configured")
        return "cdek", "delivery_create"
    if delivery_service == "YANDEX":
        if not YANDEX_DELIVERY_TOKEN:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Yandex Delivery is not configured")
        return "yandex_delivery", "delivery_create"
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order has no supported delivery service")


@admin_orders_router.post("/{order_id}/operations/{operation}", response_model=IntegrationRunRead, status_code=status.HTTP_202_ACCEPTED)
async def run_order_operation(
    order_id: int,
    operation: AdminOrderOperation,
    payload: AdminOrderOperationPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("orders.recover", write=True)),
) -> IntegrationRunRead:
    order = await _get_order(db, order_id)
    provider, internal_operation = _operation_provider(order, operation)
    existing = (await db.execute(
        select(IntegrationRun).where(IntegrationRun.idempotency_key == payload.idempotency_key)
    )).scalar_one_or_none()
    if existing is not None:
        if (
            existing.target_type != "order"
            or existing.target_id != str(order_id)
            or existing.provider != provider
            or existing.operation != internal_operation
        ):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key belongs to another operation")
        return IntegrationRunRead.model_validate(existing)

    ensure_not_stale(actual=order.updated_at, expected=payload.expected_updated_at)
    run = IntegrationRun(
        provider=provider,
        operation=internal_operation,
        status="queued",
        requested_by_user_id=context.user.id,
        target_type="order",
        target_id=str(order.id),
        attempts=0,
        max_attempts=default_max_attempts(),
        idempotency_key=payload.idempotency_key,
    )
    db.add(run)
    await db.flush()
    await add_admin_audit(
        db,
        request,
        context,
        action="order.operation.queued",
        entity_type="order",
        entity_id=order.id,
        after={"run_id": run.id, "provider": provider, "operation": internal_operation},
    )
    await db.commit()
    await db.refresh(run)
    try:
        await enqueue_integration_run(run.id)
    except Exception as error:
        run.status = "error"
        run.error = f"Failed to enqueue admin job: {error}"[:8000]
        run.finished_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin job queue is unavailable") from error
    return IntegrationRunRead.model_validate(run)


@admin_orders_router.post("/{order_id}/transition", response_model=IntegrationRunRead, status_code=status.HTTP_202_ACCEPTED)
async def transition_order(
    order_id: int,
    payload: AdminOrderTransitionPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("orders.transition", write=True)),
) -> IntegrationRunRead:
    order = await _get_order(db, order_id)
    ensure_not_stale(actual=order.updated_at, expected=payload.expected_updated_at)
    current_code = get_order_status_code(order)
    if current_code == payload.status_code:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order already has this status")
    if not transition_is_allowed(current_code, payload.status_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_transition", "from": current_code, "to": payload.status_code},
        )
    if payload.status_code == "canceled" and not (payload.reason or "").strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cancellation reason is required")
    if not order.amocrm_lead_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order is not linked to amoCRM")

    before = serialize_admin_order_detail(order).model_dump(mode="json")
    existing = (await db.execute(
        select(IntegrationRun).where(IntegrationRun.idempotency_key == payload.idempotency_key)
    )).scalar_one_or_none()
    if existing is not None:
        if (
            existing.target_type != "order"
            or existing.target_id != str(order_id)
            or existing.provider != "amocrm"
            or existing.operation != "status_transition"
        ):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key belongs to another operation")
        return IntegrationRunRead.model_validate(existing)

    run = IntegrationRun(
        provider="amocrm",
        operation="status_transition",
        status="queued",
        requested_by_user_id=context.user.id,
        target_type="order",
        target_id=str(order.id),
        attempts=0,
        max_attempts=default_max_attempts(),
        idempotency_key=payload.idempotency_key,
        input_json={
            "from_status_code": current_code,
            "to_status_code": payload.status_code,
            "target_status_id": transition_status_id(payload.status_code),
            "reason": (payload.reason or "").strip() or None,
        },
    )
    db.add(run)
    await db.flush()
    await add_admin_audit(
        db,
        request,
        context,
        action="order.transition.queued",
        entity_type="order",
        entity_id=order.id,
        before=before,
        after={"run_id": run.id, "provider": run.provider, "operation": run.operation, "target_status_code": payload.status_code},
        details={"from_status_code": current_code, "to_status_code": payload.status_code, "reason": (payload.reason or "").strip() or None},
    )
    await db.commit()
    await db.refresh(run)
    try:
        await enqueue_integration_run(run.id)
    except Exception as error:
        run.status = "error"
        run.error = f"Failed to enqueue admin job: {error}"[:8000]
        run.finished_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin job queue is unavailable") from error
    return IntegrationRunRead.model_validate(run)
