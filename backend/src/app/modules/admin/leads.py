from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette import status

from config import ufa_now
from src.app.modules.admin.helpers import ensure_not_stale
from src.app.modules.admin.schemas import (
    AdminLeadCreatePayload,
    AdminLeadDetail,
    AdminLeadNotePayload,
    AdminLeadNoteRead,
    AdminLeadRead,
    AdminLeadStageHistoryRead,
    AdminLeadUpdatePayload,
    AdminPage,
)
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.database import get_db
from src.database.models import (
    Admin,
    CrmConversation,
    CrmLead,
    CrmLeadNote,
    CrmLeadStageHistory,
    Order,
    Product,
    ProductCategory,
    User,
)

admin_leads_router = APIRouter(prefix="/leads", tags=["admin_leads"])


def _admin_name(admin: Admin | None) -> str | None:
    return f"{admin.user.name} {admin.user.surname}".strip() if admin else None


def _lead_options(*, detail: bool):
    options = [
        joinedload(CrmLead.customer),
        joinedload(CrmLead.conversation),
        joinedload(CrmLead.product),
        joinedload(CrmLead.category),
        joinedload(CrmLead.owner).joinedload(Admin.user),
        joinedload(CrmLead.converted_order),
    ]
    if detail:
        options.extend([
            selectinload(CrmLead.stage_history).joinedload(CrmLeadStageHistory.changed_by).joinedload(Admin.user),
            selectinload(CrmLead.notes).joinedload(CrmLeadNote.author).joinedload(Admin.user),
        ])
    return tuple(options)


async def _get_lead(db: AsyncSession, lead_id: int, *, detail: bool = True, lock: bool = False) -> CrmLead | None:
    stmt = (
        select(CrmLead)
        .options(*_lead_options(detail=detail))
        .where(CrmLead.id == lead_id)
        .execution_options(populate_existing=True)
    )
    if lock:
        stmt = stmt.with_for_update(of=CrmLead)
    return (await db.execute(stmt)).scalars().unique().one_or_none()


def _lead_read(lead: CrmLead, *, detail: bool) -> AdminLeadRead | AdminLeadDetail:
    base = {
        "id": lead.id,
        "title": lead.title,
        "source": lead.source,
        "status": lead.status,
        "priority": lead.priority,
        "score": lead.score,
        "customer_user_id": lead.customer_user_id,
        "customer_name": f"{lead.customer.name} {lead.customer.surname}".strip() if lead.customer else lead.contact_name,
        "conversation_id": lead.conversation_id,
        "product_id": lead.product_id,
        "product_name": lead.product.name if lead.product else None,
        "category_id": lead.category_id,
        "category_name": lead.category.name if lead.category else None,
        "owner_user_id": lead.owner_user_id,
        "owner_name": _admin_name(lead.owner),
        "converted_order_id": lead.converted_order_id,
        "converted_order_code": lead.converted_order.order_code if lead.converted_order else None,
        "contact_name": lead.contact_name,
        "contact_email": lead.contact_email,
        "contact_phone": lead.contact_phone,
        "description": lead.description,
        "next_action_at": lead.next_action_at,
        "lost_reason": lead.lost_reason,
        "converted_at": lead.converted_at,
        "lost_at": lead.lost_at,
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
    }
    if not detail:
        return AdminLeadRead.model_validate(base)
    return AdminLeadDetail.model_validate({
        **base,
        "stage_history": [
            AdminLeadStageHistoryRead(
                id=item.id,
                from_status=item.from_status,
                to_status=item.to_status,
                changed_by_name=_admin_name(item.changed_by),
                reason=item.reason,
                created_at=item.created_at,
            )
            for item in lead.stage_history
        ],
        "notes": [
            AdminLeadNoteRead(
                id=item.id,
                body=item.body,
                author_name=_admin_name(item.author),
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in lead.notes
        ],
    })


async def _validate_lead_links(
    db: AsyncSession,
    *,
    customer_user_id: int | None,
    conversation_id: int | None,
    product_id: int | None,
    category_id: int | None,
    owner_user_id: int | None,
    converted_order_id: int | None,
) -> tuple[User | None, CrmConversation | None, Order | None]:
    customer = await db.get(User, customer_user_id) if customer_user_id is not None else None
    if customer_user_id is not None and customer is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Customer not found")
    conversation = await db.get(CrmConversation, conversation_id) if conversation_id is not None else None
    if conversation_id is not None and conversation is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Support conversation not found")
    if conversation is not None:
        if customer_user_id is not None and conversation.customer_user_id != customer_user_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Conversation belongs to another customer")
        customer = customer or await db.get(User, conversation.customer_user_id)
    if product_id is not None and await db.get(Product, product_id) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Product not found")
    if category_id is not None and await db.get(ProductCategory, category_id) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Category not found")
    if owner_user_id is not None:
        owner = await db.get(Admin, owner_user_id)
        if owner is None or not owner.is_active:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Owner is not an active administrator")
    order = await db.get(Order, converted_order_id) if converted_order_id is not None else None
    if converted_order_id is not None and order is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Converted order not found")
    resolved_customer_id = customer.id if customer else (conversation.customer_user_id if conversation else None)
    if order is not None and resolved_customer_id is not None and order.user_id != resolved_customer_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Converted order belongs to another customer")
    return customer, conversation, order


@admin_leads_router.get("", response_model=AdminPage[AdminLeadRead])
async def list_leads(
    q: str | None = Query(default=None, max_length=120),
    lead_status: str | None = Query(default=None, alias="status", pattern="^(all|active|new|contacted|interested|waiting|converted|lost)$"),
    priority: str | None = Query(default=None, pattern="^(low|normal|high|urgent)$"),
    source: str | None = Query(default=None, max_length=48),
    owner_user_id: int | None = Query(default=None, ge=1),
    customer_user_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("leads.read")),
) -> AdminPage[AdminLeadRead]:
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(
            CrmLead.title.ilike(pattern),
            CrmLead.contact_name.ilike(pattern),
            CrmLead.contact_email.ilike(pattern),
            CrmLead.contact_phone.ilike(pattern),
            CrmLead.customer.has(or_(
                func.concat_ws(" ", User.name, User.surname).ilike(pattern),
                User.email.ilike(pattern),
                User.phone_number.ilike(pattern),
            )),
        ))
    if lead_status == "active":
        filters.append(CrmLead.status.in_(("new", "contacted", "interested", "waiting")))
    elif lead_status and lead_status != "all":
        filters.append(CrmLead.status == lead_status)
    if priority:
        filters.append(CrmLead.priority == priority)
    if source:
        filters.append(CrmLead.source == source)
    if owner_user_id:
        filters.append(CrmLead.owner_user_id == owner_user_id)
    if customer_user_id:
        filters.append(CrmLead.customer_user_id == customer_user_id)

    total = int((await db.execute(select(func.count(CrmLead.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(
        select(CrmLead)
        .options(*_lead_options(detail=False))
        .where(*filters)
        .order_by(
            CrmLead.status.in_(("converted", "lost")),
            CrmLead.next_action_at.asc().nullslast(),
            CrmLead.score.desc(),
            CrmLead.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )).scalars().unique().all())
    return AdminPage(
        items=[_lead_read(item, detail=False) for item in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@admin_leads_router.get("/{lead_id}", response_model=AdminLeadDetail)
async def get_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("leads.read")),
) -> AdminLeadDetail:
    lead = await _get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return _lead_read(lead, detail=True)


@admin_leads_router.post("", response_model=AdminLeadDetail, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: AdminLeadCreatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("leads.manage", write=True)),
) -> AdminLeadDetail:
    customer, conversation, _ = await _validate_lead_links(
        db,
        customer_user_id=payload.customer_user_id,
        conversation_id=payload.conversation_id,
        product_id=payload.product_id,
        category_id=payload.category_id,
        owner_user_id=payload.owner_user_id,
        converted_order_id=None,
    )
    owner_user_id = payload.owner_user_id or context.user.id
    values = payload.model_dump()
    values.update({
        "title": payload.title.strip(),
        "description": payload.description.strip() if payload.description else None,
        "customer_user_id": customer.id if customer else (conversation.customer_user_id if conversation else payload.customer_user_id),
        "owner_user_id": owner_user_id,
        "created_by_user_id": context.user.id,
        "contact_name": payload.contact_name or (f"{customer.name} {customer.surname}".strip() if customer else None),
        "contact_email": str(payload.contact_email) if payload.contact_email else (customer.email if customer else None),
        "contact_phone": payload.contact_phone or (customer.phone_number if customer else None),
    })
    lead = CrmLead(**values)
    db.add(lead)
    await db.flush()
    db.add(CrmLeadStageHistory(
        lead_id=lead.id,
        from_status=None,
        to_status="new",
        changed_by_user_id=context.user.id,
        reason="Lead created",
    ))
    await add_admin_audit(
        db,
        request,
        context,
        action="lead.create",
        entity_type="lead",
        entity_id=lead.id,
        after={"title": lead.title, "source": lead.source, "customer_user_id": lead.customer_user_id},
    )
    await db.commit()
    result = await _get_lead(db, lead.id)
    if result is None:
        raise RuntimeError("Lead could not be reloaded")
    return _lead_read(result, detail=True)


@admin_leads_router.patch("/{lead_id}", response_model=AdminLeadDetail)
async def update_lead(
    lead_id: int,
    payload: AdminLeadUpdatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("leads.manage", write=True)),
) -> AdminLeadDetail:
    lead = await _get_lead(db, lead_id, lock=True)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    ensure_not_stale(actual=lead.updated_at, expected=payload.expected_updated_at)
    values = payload.model_dump(exclude={"expected_updated_at", "stage_reason"}, exclude_unset=True)
    prospective_owner = values.get("owner_user_id", lead.owner_user_id)
    prospective_product = values.get("product_id", lead.product_id)
    prospective_category = values.get("category_id", lead.category_id)
    prospective_order = values.get("converted_order_id", lead.converted_order_id)
    await _validate_lead_links(
        db,
        customer_user_id=lead.customer_user_id,
        conversation_id=lead.conversation_id,
        product_id=prospective_product,
        category_id=prospective_category,
        owner_user_id=prospective_owner,
        converted_order_id=prospective_order,
    )
    before = _lead_read(lead, detail=False).model_dump(mode="json")
    previous_status = lead.status
    for field, value in values.items():
        if field in {"title", "description", "lost_reason"} and isinstance(value, str):
            value = value.strip() or None
        setattr(lead, field, value)
    now = ufa_now()
    if lead.status != previous_status:
        db.add(CrmLeadStageHistory(
            lead_id=lead.id,
            from_status=previous_status,
            to_status=lead.status,
            changed_by_user_id=context.user.id,
            reason=(payload.stage_reason or payload.lost_reason or "").strip() or None,
        ))
    if lead.status == "converted":
        lead.converted_at = lead.converted_at or now
        lead.lost_at = None
        lead.lost_reason = None
    elif lead.status == "lost":
        lead.lost_at = lead.lost_at or now
        lead.converted_at = None
        lead.converted_order_id = None
    else:
        lead.converted_at = None
        lead.lost_at = None
        lead.lost_reason = None
        lead.converted_order_id = None
    await db.flush()
    await add_admin_audit(
        db,
        request,
        context,
        action="lead.update",
        entity_type="lead",
        entity_id=lead.id,
        before=before,
        after=_lead_read(lead, detail=False).model_dump(mode="json"),
    )
    await db.commit()
    result = await _get_lead(db, lead.id)
    if result is None:
        raise RuntimeError("Lead could not be reloaded")
    return _lead_read(result, detail=True)


@admin_leads_router.post("/{lead_id}/notes", response_model=AdminLeadDetail, status_code=status.HTTP_201_CREATED)
async def add_lead_note(
    lead_id: int,
    payload: AdminLeadNotePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("leads.manage", write=True)),
) -> AdminLeadDetail:
    lead = await _get_lead(db, lead_id, lock=True)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    note = CrmLeadNote(lead_id=lead.id, author_user_id=context.user.id, body=payload.body.strip())
    db.add(note)
    await db.flush()
    await add_admin_audit(
        db,
        request,
        context,
        action="lead.note",
        entity_type="lead",
        entity_id=lead.id,
        after={"note_id": note.id},
    )
    await db.commit()
    result = await _get_lead(db, lead.id)
    if result is None:
        raise RuntimeError("Lead could not be reloaded")
    return _lead_read(result, detail=True)
