from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.app.modules.admin.schemas import (
    AdminDashboardPreferencePayload,
    AdminDashboardPreferenceRead,
    DashboardMetrics,
    DashboardResponse,
    DashboardTrendPoint,
    SearchResponse,
    SearchResultItem,
)
from src.app.modules.admin.helpers import ensure_not_stale
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.database import get_db
from src.database.models import AdminDashboardPreference, AdminTask, Basket, BasketItem, IntegrationRun, Order, Product, Review, User, Variant
from starlette import status

admin_overview_router = APIRouter(tags=["admin_overview"])

DEFAULT_DASHBOARD_WIDGETS = ["revenue", "paid_orders", "average_order", "new_customers", "revenue_trend", "attention", "sla"]
DASHBOARD_WIDGETS = frozenset(DEFAULT_DASHBOARD_WIDGETS)


@admin_overview_router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    days: int = Query(default=30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("dashboard.read")),
) -> DashboardResponse:
    now = ufa_now()
    start = now - timedelta(days=days)
    paid_filter = (Order.is_paid.is_(True), Order.is_canceled.is_(False), Order.created_at >= start)
    revenue, paid_orders = (await db.execute(select(
        func.coalesce(func.sum(Order.grand_total), 0),
        func.count(Order.id),
    ).where(*paid_filter))).one()
    revenue_decimal = Decimal(revenue or 0)
    paid_count = int(paid_orders or 0)
    new_customers = int((await db.execute(select(func.count(User.id)).where(User.created_at >= start))).scalar_one())
    failed_payments = int((await db.execute(select(func.count(Order.id)).where(
        Order.created_at >= start,
        Order.payment_status.in_(("error", "canceled", "refunded")),
    ))).scalar_one())
    pending_reviews = int((await db.execute(select(func.count(Review.id)).where(
        Review.moderated.is_(False),
        Review.rejected_at.is_(None),
    ))).scalar_one())
    low_stock = int((await db.execute(select(func.count(Variant.id)).where(
        Variant.archived.is_(False),
        Variant.stock <= 3,
    ))).scalar_one())
    abandoned = int((await db.execute(select(func.count(func.distinct(Basket.id))).join(BasketItem).where(
        Basket.updated_at <= now - timedelta(hours=24),
    ))).scalar_one())
    integration_errors = int((await db.execute(select(func.count(IntegrationRun.id)).where(
        IntegrationRun.status == "error",
        IntegrationRun.started_at >= start,
    ))).scalar_one())
    overdue_tasks = int((await db.execute(select(func.count(AdminTask.id)).where(
        AdminTask.status.in_(("open", "in_progress")),
        AdminTask.due_at < now,
    ))).scalar_one())
    sla_breached_tasks = int((await db.execute(select(func.count(AdminTask.id)).where(
        AdminTask.status.in_(("open", "in_progress")),
        AdminTask.sla_breached_at.is_not(None),
    ))).scalar_one())
    completed_sla = int((await db.execute(select(func.count(AdminTask.id)).where(
        AdminTask.status == "done",
        AdminTask.completed_at >= start,
        AdminTask.resolution_due_at.is_not(None),
    ))).scalar_one())
    on_time_sla = int((await db.execute(select(func.count(AdminTask.id)).where(
        AdminTask.status == "done",
        AdminTask.completed_at >= start,
        AdminTask.completed_at <= AdminTask.resolution_due_at,
    ))).scalar_one())
    sla_compliance = (Decimal(on_time_sla) / Decimal(completed_sla) * 100).quantize(Decimal("0.1")) if completed_sla else Decimal("100.0")

    trend_rows = (await db.execute(select(
        func.date(Order.payment_paid_at).label("day"),
        func.coalesce(func.sum(Order.grand_total), 0).label("revenue"),
        func.count(Order.id).label("orders"),
    ).where(
        Order.is_paid.is_(True),
        Order.is_canceled.is_(False),
        Order.payment_paid_at.is_not(None),
        Order.payment_paid_at >= start,
    ).group_by(func.date(Order.payment_paid_at)).order_by(func.date(Order.payment_paid_at)))).all()

    return DashboardResponse(
        metrics=DashboardMetrics(
            revenue=revenue_decimal,
            paid_orders=paid_count,
            average_order_value=(revenue_decimal / paid_count).quantize(Decimal("0.01")) if paid_count else Decimal("0.00"),
            new_customers=new_customers,
            failed_payments=failed_payments,
            pending_reviews=pending_reviews,
            low_stock_variants=low_stock,
            abandoned_baskets=abandoned,
            integration_errors=integration_errors,
            overdue_tasks=overdue_tasks,
            sla_breached_tasks=sla_breached_tasks,
            sla_compliance_percent=sla_compliance,
        ),
        revenue_trend=[DashboardTrendPoint(day=row.day, revenue=Decimal(row.revenue or 0), orders=int(row.orders)) for row in trend_rows],
    )


@admin_overview_router.get("/dashboard/preferences", response_model=AdminDashboardPreferenceRead)
async def get_dashboard_preferences(
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("dashboard.read")),
) -> AdminDashboardPreferenceRead:
    row = (await db.execute(select(AdminDashboardPreference).where(
        AdminDashboardPreference.owner_user_id == context.user.id
    ))).scalar_one_or_none()
    return AdminDashboardPreferenceRead(
        widgets=row.widgets_json if row and row.widgets_json else DEFAULT_DASHBOARD_WIDGETS,
        updated_at=row.updated_at if row else None,
    )


@admin_overview_router.put("/dashboard/preferences", response_model=AdminDashboardPreferenceRead)
async def update_dashboard_preferences(
    payload: AdminDashboardPreferencePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("dashboard.read", write=True)),
) -> AdminDashboardPreferenceRead:
    widgets = list(dict.fromkeys(payload.widgets))
    unknown = sorted(set(widgets) - DASHBOARD_WIDGETS)
    if unknown:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"unknown_widgets": unknown})
    row = (await db.execute(select(AdminDashboardPreference).where(
        AdminDashboardPreference.owner_user_id == context.user.id
    ))).scalar_one_or_none()
    before = None
    if row is None:
        if payload.expected_updated_at is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dashboard preferences no longer exist")
        row = AdminDashboardPreference(owner_user_id=context.user.id, widgets_json=widgets)
        db.add(row)
    else:
        if payload.expected_updated_at is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dashboard preferences already exist")
        ensure_not_stale(actual=row.updated_at, expected=payload.expected_updated_at)
        before = {"widgets": row.widgets_json}
        row.widgets_json = widgets
    await db.flush()
    await add_admin_audit(db, request, context, action="dashboard.preferences.update", entity_type="dashboard_preference", entity_id=row.id, before=before, after={"widgets": widgets})
    await db.commit()
    await db.refresh(row)
    return AdminDashboardPreferenceRead(widgets=row.widgets_json, updated_at=row.updated_at)


@admin_overview_router.get("/search", response_model=SearchResponse)
async def global_search(
    q: str = Query(min_length=2, max_length=100),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("dashboard.read")),
) -> SearchResponse:
    pattern = f"%{q.strip()}%"
    order_rows = list((await db.execute(select(Order).where(or_(
        Order.order_code.ilike(pattern),
        Order.payment_invoice_id.ilike(pattern),
    )).order_by(Order.created_at.desc()).limit(5))).scalars().all())
    customer_rows = list((await db.execute(select(User).where(or_(
        User.email.ilike(pattern),
        User.phone_number.ilike(pattern),
        User.name.ilike(pattern),
        User.surname.ilike(pattern),
    )).order_by(User.id.desc()).limit(5))).scalars().all())
    product_rows = list((await db.execute(select(Product).where(or_(
        Product.name.ilike(pattern),
        Product.sku.ilike(pattern),
    )).order_by(Product.id.desc()).limit(5))).scalars().all())

    items = [SearchResultItem(type="order", id=row.id, title=f"Заказ {row.order_code}", subtitle=f"{row.status} · {row.grand_total} {row.currency}", path=f"/sales/orders/{row.id}") for row in order_rows]
    items.extend(SearchResultItem(type="customer", id=row.id, title=f"{row.name} {row.surname}".strip(), subtitle=row.email or row.phone_number or f"ID {row.id}", path=f"/customers/{row.id}") for row in customer_rows)
    items.extend(SearchResultItem(type="product", id=row.id, title=row.name, subtitle=row.sku, path=f"/catalog/products/{row.id}") for row in product_rows)
    return SearchResponse(items=items)
