from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette import status

from config import ufa_now
from src.app.modules.admin.helpers import ensure_not_stale
from src.app.modules.admin.schemas import (
    AdminNoteCreate,
    AdminNoteRead,
    AdminPage,
    CustomerDetail,
    CustomerListItem,
    CustomerStatusPayload,
)
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.database import get_db
from src.database.models import (
    Admin,
    AdminNote,
    Basket,
    BasketItem,
    FavouredProduct,
    Order,
    ReferralProfile,
    User,
    UserProductRecommendationSignal,
    UserPushToken,
    UserSession,
)

admin_customers_router = APIRouter(prefix="/customers", tags=["admin_customers"])


def _orders_aggregate():
    return select(
        Order.user_id.label("user_id"),
        func.count(Order.id).label("orders_count"),
        func.coalesce(func.sum(Order.grand_total).filter(Order.is_paid.is_(True), Order.is_canceled.is_(False)), 0).label("paid_total"),
        func.max(Order.created_at).label("last_order_at"),
    ).group_by(Order.user_id).subquery()


def _customer_item(user: User, orders_count, paid_total, last_order_at) -> CustomerListItem:
    return CustomerListItem(
        id=user.id,
        name=user.name,
        surname=user.surname,
        email=user.email,
        phone_number=user.phone_number,
        is_active=user.is_active,
        is_verified=user.is_verified,
        telegram_username=user.telegram_username,
        orders_count=int(orders_count or 0),
        paid_total=Decimal(paid_total or 0),
        last_order_at=last_order_at,
        last_active_at=user.last_active_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@admin_customers_router.get("", response_model=AdminPage[CustomerListItem])
async def list_customers(
    q: str | None = Query(default=None, max_length=100),
    is_active: bool | None = None,
    is_verified: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("customers.read")),
) -> AdminPage[CustomerListItem]:
    aggregate = _orders_aggregate()
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(
            User.email.ilike(pattern),
            User.phone_number.ilike(pattern),
            User.name.ilike(pattern),
            User.surname.ilike(pattern),
            User.telegram_username.ilike(pattern),
        ))
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    if is_verified is not None:
        filters.append(User.is_verified.is_(is_verified))
    total = int((await db.execute(select(func.count(User.id)).where(*filters))).scalar_one())
    rows = (await db.execute(select(
        User,
        aggregate.c.orders_count,
        aggregate.c.paid_total,
        aggregate.c.last_order_at,
    ).outerjoin(aggregate, aggregate.c.user_id == User.id).where(*filters).order_by(User.created_at.desc(), User.id.desc()).offset(offset).limit(limit))).all()
    return AdminPage(items=[_customer_item(*row) for row in rows], total=total, limit=limit, offset=offset)


async def _get_customer_base(db: AsyncSession, customer_id: int):
    aggregate = _orders_aggregate()
    row = (await db.execute(select(
        User,
        aggregate.c.orders_count,
        aggregate.c.paid_total,
        aggregate.c.last_order_at,
    ).outerjoin(aggregate, aggregate.c.user_id == User.id).where(User.id == customer_id))).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return row


async def _customer_detail(db: AsyncSession, customer_id: int) -> CustomerDetail:
    user, orders_count, paid_total, last_order_at = await _get_customer_base(db, customer_id)
    base = _customer_item(user, orders_count, paid_total, last_order_at).model_dump()
    basket_row = (await db.execute(select(
        func.count(BasketItem.id),
        func.coalesce(func.sum(BasketItem.price * BasketItem.quantity), 0),
    ).select_from(Basket).outerjoin(BasketItem, BasketItem.basket_id == Basket.id).where(Basket.user_id == customer_id))).one()
    favourites = int((await db.execute(select(func.count(FavouredProduct.id)).where(FavouredProduct.user_id == customer_id))).scalar_one())
    push_tokens = int((await db.execute(select(func.count(UserPushToken.id)).where(UserPushToken.user_id == customer_id))).scalar_one())
    referral = (await db.execute(select(ReferralProfile).where(ReferralProfile.user_id == customer_id))).scalar_one_or_none()
    signal_row = (await db.execute(select(
        func.coalesce(func.sum(UserProductRecommendationSignal.view_count), 0),
        func.coalesce(func.sum(UserProductRecommendationSignal.cart_quantity), 0),
    ).where(UserProductRecommendationSignal.user_id == customer_id))).one()
    notes = list((await db.execute(select(AdminNote).options(
        selectinload(AdminNote.author).joinedload(Admin.user),
    ).where(AdminNote.customer_user_id == customer_id).order_by(AdminNote.created_at.desc()))).scalars().all())

    return CustomerDetail(
        **base,
        contact_id=user.contact_id,
        moysklad_counterparty_id=str(user.moysklad_counterparty_id) if user.moysklad_counterparty_id else None,
        promo_code=user.promo_code,
        basket_items=int(basket_row[0] or 0),
        basket_total=Decimal(basket_row[1] or 0),
        favourites_count=favourites,
        push_tokens_count=push_tokens,
        referral_discount_base_total=referral.referral_discount_base_total if referral else Decimal("0.00"),
        referral_discount_percent=referral.current_discount_percent if referral else Decimal("0.00"),
        total_product_views=int(signal_row[0] or 0),
        total_cart_quantity=int(signal_row[1] or 0),
        notes=[AdminNoteRead(
            id=note.id,
            body=note.body,
            author_name=(f"{note.author.user.name} {note.author.user.surname}".strip() if note.author else "Удалённый сотрудник"),
            created_at=note.created_at,
            updated_at=note.updated_at,
        ) for note in notes],
    )


@admin_customers_router.get("/{customer_id}", response_model=CustomerDetail)
async def get_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("customers.read")),
) -> CustomerDetail:
    return await _customer_detail(db, customer_id)


@admin_customers_router.patch("/{customer_id}/status", response_model=CustomerDetail)
async def update_customer_status(
    customer_id: int,
    payload: CustomerStatusPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("customers.manage", write=True)),
) -> CustomerDetail:
    user = await db.get(User, customer_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    ensure_not_stale(actual=user.updated_at, expected=payload.expected_updated_at)
    before = {"is_active": user.is_active, "updated_at": user.updated_at}
    user.is_active = payload.is_active
    if not payload.is_active:
        now = ufa_now()
        rows = list((await db.execute(select(UserSession).where(UserSession.user_id == customer_id, UserSession.revoked_at.is_(None)))).scalars().all())
        for session in rows:
            session.revoked_at = now
    await db.flush()
    await add_admin_audit(db, request, context, action="customer.status", entity_type="customer", entity_id=user.id, before=before, after={"is_active": user.is_active})
    await db.commit()
    return await _customer_detail(db, customer_id)


@admin_customers_router.post("/{customer_id}/notes", response_model=AdminNoteRead, status_code=status.HTTP_201_CREATED)
async def create_customer_note(
    customer_id: int,
    payload: AdminNoteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("customers.notes", write=True)),
) -> AdminNoteRead:
    if await db.get(User, customer_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    note = AdminNote(customer_user_id=customer_id, author_user_id=context.user.id, body=payload.body.strip())
    db.add(note)
    await db.flush()
    await add_admin_audit(db, request, context, action="customer.note.create", entity_type="customer", entity_id=customer_id, after={"note_id": note.id, "body": note.body})
    await db.commit()
    await db.refresh(note)
    return AdminNoteRead(id=note.id, body=note.body, author_name=f"{context.user.name} {context.user.surname}".strip(), created_at=note.created_at, updated_at=note.updated_at)
