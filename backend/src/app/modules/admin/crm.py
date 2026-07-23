import csv
import io

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette import status

from config import ufa_now
from src.app.modules.admin.helpers import ensure_not_stale
from src.app.modules.admin.schemas import (
    AdminAudiencePreview,
    AdminAudienceSample,
    AdminAssigneeOption,
    AdminCustomerSegmentHistoryRead,
    AdminCustomerSegmentPayload,
    AdminCustomerSegmentRead,
    AdminCustomerSegmentSnapshotRead,
    AdminCustomerSegmentUpdatePayload,
    AdminPage,
    AdminTaskCreatePayload,
    AdminTaskRead,
    AdminTaskUpdatePayload,
)
from src.app.services.admin import AdminContext, add_admin_audit, apply_task_sla, require_permission, resolve_task_sla_alert
from src.app.services.admin.audiences import (
    MAX_SEGMENT_EXPORT,
    MAX_SEGMENT_PREVIEW,
    build_audience_query,
    build_static_segment_query,
    count_segment_audience,
    list_audience_ids,
    list_segment_audience_ids,
    normalize_segment_filters,
)
from src.database import get_db
from src.database.models import Admin, AdminCustomerSegment, AdminCustomerSegmentHistory, AdminCustomerSegmentSnapshotItem, AdminPushCampaign, AdminTask, Order, User

admin_crm_router = APIRouter(tags=["admin_crm"])


def _admin_name(admin: Admin | None) -> str | None:
    return f"{admin.user.name} {admin.user.surname}".strip() if admin else None


def _task_options():
    return (
        joinedload(AdminTask.customer),
        joinedload(AdminTask.order),
        joinedload(AdminTask.assignee).joinedload(Admin.user),
        joinedload(AdminTask.created_by).joinedload(Admin.user),
    )


def _task_read(task: AdminTask) -> AdminTaskRead:
    return AdminTaskRead(
        id=task.id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        due_at=task.due_at,
        completed_at=task.completed_at,
        sla_policy_id=task.sla_policy_id,
        response_due_at=task.response_due_at,
        resolution_due_at=task.resolution_due_at,
        first_started_at=task.first_started_at,
        sla_breached_at=task.sla_breached_at,
        customer_user_id=task.customer_user_id,
        customer_name=f"{task.customer.name} {task.customer.surname}".strip() if task.customer else None,
        order_id=task.order_id,
        order_code=task.order.order_code if task.order else None,
        assignee_user_id=task.assignee_user_id,
        assignee_name=_admin_name(task.assignee) or "—",
        created_by_name=_admin_name(task.created_by),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


async def _get_task(db: AsyncSession, task_id: int) -> AdminTask:
    task = (await db.execute(
        select(AdminTask).options(*_task_options()).where(AdminTask.id == task_id).execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@admin_crm_router.get("/tasks/assignees", response_model=list[AdminAssigneeOption])
async def list_task_assignees(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("tasks.read")),
) -> list[AdminAssigneeOption]:
    rows = list((await db.execute(
        select(Admin).options(joinedload(Admin.user)).where(Admin.is_active.is_(True)).order_by(Admin.user_id)
    )).scalars().all())
    return [AdminAssigneeOption(user_id=row.user_id, name=_admin_name(row) or str(row.user_id)) for row in rows]


async def _validate_task_links(
    db: AsyncSession,
    *,
    customer_user_id: int | None,
    order_id: int | None,
    assignee_user_id: int,
) -> None:
    if customer_user_id is not None and await db.get(User, customer_user_id) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Customer not found")
    order = await db.get(Order, order_id) if order_id is not None else None
    if order_id is not None and order is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Order not found")
    if order is not None and customer_user_id is not None and order.user_id != customer_user_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Order belongs to another customer")
    assignee = await db.get(Admin, assignee_user_id)
    if assignee is None or not assignee.is_active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Assignee is not an active administrator")


@admin_crm_router.get("/tasks", response_model=AdminPage[AdminTaskRead])
async def list_tasks(
    q: str | None = Query(default=None, max_length=100),
    task_status: str | None = Query(default=None, alias="status", pattern="^(active|open|in_progress|done|canceled)$"),
    priority: str | None = Query(default=None, pattern="^(low|normal|high|urgent)$"),
    assignee_user_id: int | None = Query(default=None, ge=1),
    customer_user_id: int | None = Query(default=None, ge=1),
    order_id: int | None = Query(default=None, ge=1),
    overdue: bool | None = None,
    sla_breached: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("tasks.read")),
) -> AdminPage[AdminTaskRead]:
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(AdminTask.title.ilike(pattern), AdminTask.description.ilike(pattern)))
    if task_status == "active":
        filters.append(AdminTask.status.in_(("open", "in_progress")))
    elif task_status:
        filters.append(AdminTask.status == task_status)
    if priority:
        filters.append(AdminTask.priority == priority)
    if assignee_user_id:
        filters.append(AdminTask.assignee_user_id == assignee_user_id)
    if customer_user_id:
        filters.append(AdminTask.customer_user_id == customer_user_id)
    if order_id:
        filters.append(AdminTask.order_id == order_id)
    if overdue is True:
        filters.extend((AdminTask.due_at < ufa_now(), AdminTask.status.in_(("open", "in_progress"))))
    if sla_breached is True:
        filters.append(AdminTask.sla_breached_at.is_not(None))
    total = int((await db.execute(select(func.count(AdminTask.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(
        select(AdminTask)
        .options(*_task_options())
        .where(*filters)
        .order_by(AdminTask.status.in_(("done", "canceled")), AdminTask.due_at.asc().nullslast(), AdminTask.id.desc())
        .offset(offset)
        .limit(limit)
    )).scalars().unique().all())
    return AdminPage(items=[_task_read(row) for row in rows], total=total, limit=limit, offset=offset)


@admin_crm_router.post("/tasks", response_model=AdminTaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: AdminTaskCreatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("tasks.manage", write=True)),
) -> AdminTaskRead:
    assignee_user_id = payload.assignee_user_id or context.user.id
    await _validate_task_links(
        db,
        customer_user_id=payload.customer_user_id,
        order_id=payload.order_id,
        assignee_user_id=assignee_user_id,
    )
    task = AdminTask(
        **payload.model_dump(exclude={"assignee_user_id", "title", "description"}),
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        assignee_user_id=assignee_user_id,
        created_by_user_id=context.user.id,
    )
    await apply_task_sla(db, task, origin=ufa_now())
    db.add(task)
    await db.flush()
    await add_admin_audit(db, request, context, action="task.create", entity_type="task", entity_id=task.id, after={"title": task.title, "assignee_user_id": assignee_user_id})
    await db.commit()
    return _task_read(await _get_task(db, task.id))


@admin_crm_router.patch("/tasks/{task_id}", response_model=AdminTaskRead)
async def update_task(
    task_id: int,
    payload: AdminTaskUpdatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("tasks.manage", write=True)),
) -> AdminTaskRead:
    task = await _get_task(db, task_id)
    ensure_not_stale(actual=task.updated_at, expected=payload.expected_updated_at)
    values = payload.model_dump(exclude={"expected_updated_at"}, exclude_unset=True)
    if "title" in values and values["title"] is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Task title cannot be empty")
    assignee_user_id = values.get("assignee_user_id", task.assignee_user_id)
    customer_user_id = values.get("customer_user_id", task.customer_user_id)
    order_id = values.get("order_id", task.order_id)
    await _validate_task_links(db, customer_user_id=customer_user_id, order_id=order_id, assignee_user_id=assignee_user_id)
    before = _task_read(task).model_dump(mode="json")
    previous_priority = task.priority
    previous_status = task.status
    for field, value in values.items():
        if field in {"title", "description"} and isinstance(value, str):
            value = value.strip() or None
        setattr(task, field, value)
    now = ufa_now()
    if task.priority != previous_priority and task.status in {"open", "in_progress"}:
        await apply_task_sla(db, task, origin=task.created_at)
    if task.status == "in_progress" and task.first_started_at is None:
        task.first_started_at = now
    if previous_status in {"done", "canceled"} and task.status in {"open", "in_progress"}:
        await apply_task_sla(db, task, origin=now)
        task.sla_breached_at = None
    if task.status == "done" and task.completed_at is None:
        task.completed_at = now
    elif task.status != "done":
        task.completed_at = None
    if task.status in {"done", "canceled"}:
        await resolve_task_sla_alert(db, task.id)
    await db.flush()
    result = _task_read(await _get_task(db, task.id))
    await add_admin_audit(db, request, context, action="task.update", entity_type="task", entity_id=task.id, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    return result


def _segment_snapshot(segment: AdminCustomerSegment) -> dict:
    return {
        "name": segment.name,
        "filters_json": segment.filters_json,
        "is_shared": segment.is_shared,
        "segment_type": segment.segment_type,
        "snapshot_version": segment.snapshot_version,
        "snapshot_count": segment.snapshot_count,
        "snapshot_at": segment.snapshot_at.isoformat() if segment.snapshot_at else None,
    }


def _segment_read(segment: AdminCustomerSegment, audience_count: int, push_reachable_count: int) -> AdminCustomerSegmentRead:
    return AdminCustomerSegmentRead(
        id=segment.id,
        owner_user_id=segment.owner_user_id,
        owner_name=_admin_name(segment.owner) or "—",
        name=segment.name,
        filters_json=segment.filters_json,
        is_shared=segment.is_shared,
        segment_type=segment.segment_type,
        audience_count=audience_count,
        push_reachable_count=push_reachable_count,
        snapshot_version=segment.snapshot_version,
        snapshot_at=segment.snapshot_at,
        snapshot_count=segment.snapshot_count,
        created_at=segment.created_at,
        updated_at=segment.updated_at,
    )


def _visible_segment_filter(context: AdminContext):
    return or_(AdminCustomerSegment.owner_user_id == context.user.id, AdminCustomerSegment.is_shared.is_(True))


async def _get_visible_segment(db: AsyncSession, context: AdminContext, segment_id: int) -> AdminCustomerSegment:
    segment = (await db.execute(
        select(AdminCustomerSegment)
        .options(joinedload(AdminCustomerSegment.owner).joinedload(Admin.user))
        .where(AdminCustomerSegment.id == segment_id, _visible_segment_filter(context))
    )).scalar_one_or_none()
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    return segment


async def _segment_counts(db: AsyncSession, segment: AdminCustomerSegment) -> tuple[int, int]:
    return (
        await count_segment_audience(db, segment),
        await count_segment_audience(db, segment, require_push=True, require_active=True),
    )


async def _record_segment_history(
    db: AsyncSession,
    *,
    segment: AdminCustomerSegment,
    context: AdminContext,
    action: str,
    before: dict | None,
    after: dict | None,
    metadata: dict | None = None,
) -> None:
    db.add(AdminCustomerSegmentHistory(
        segment_id=segment.id,
        actor_user_id=context.user.id,
        action=action,
        before_json=before,
        after_json=after,
        metadata_json=metadata or {},
    ))
    await db.flush()


def _admin_actor_name(admin: Admin | None) -> str | None:
    if admin is None:
        return None
    full_name = f"{admin.user.name} {admin.user.surname}".strip()
    return full_name or admin.user.email


def _segment_history_read(row: AdminCustomerSegmentHistory) -> AdminCustomerSegmentHistoryRead:
    return AdminCustomerSegmentHistoryRead(
        id=row.id,
        action=row.action,
        actor_name=_admin_actor_name(row.actor),
        before_json=row.before_json,
        after_json=row.after_json,
        metadata_json=row.metadata_json or {},
        created_at=row.created_at,
    )


async def _preview(db: AsyncSession, filters_json: dict) -> AdminAudiencePreview:
    normalized = normalize_segment_filters(filters_json)
    pseudo_segment = AdminCustomerSegment(id=0, owner_user_id=0, name="Preview", filters_json=normalized, is_shared=False, segment_type="dynamic")
    count, push_count = await _segment_counts(db, pseudo_segment)
    rows = (await db.execute(build_audience_query(normalized).order_by(User.created_at.desc()).limit(MAX_SEGMENT_PREVIEW))).all()
    return AdminAudiencePreview(
        count=count,
        push_reachable_count=push_count,
        sample=[AdminAudienceSample(
            id=user.id,
            name=user.name,
            surname=user.surname,
            email=user.email,
            phone_number=user.phone_number,
            orders_count=int(orders_count or 0),
            paid_total=paid_total or 0,
            last_order_at=last_order_at,
        ) for user, orders_count, paid_total, last_order_at in rows],
    )


@admin_crm_router.post("/segments/preview", response_model=AdminAudiencePreview)
async def preview_segment(
    payload: AdminCustomerSegmentPayload,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("segments.read")),
) -> AdminAudiencePreview:
    try:
        filters_json = normalize_segment_filters(payload.filters_json)
    except (ValidationError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return await _preview(db, filters_json)


@admin_crm_router.get("/segments", response_model=list[AdminCustomerSegmentRead])
async def list_segments(
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("segments.read")),
) -> list[AdminCustomerSegmentRead]:
    rows = list((await db.execute(
        select(AdminCustomerSegment)
        .options(joinedload(AdminCustomerSegment.owner).joinedload(Admin.user))
        .where(_visible_segment_filter(context))
        .order_by(AdminCustomerSegment.name)
    )).scalars().all())
    return [
        _segment_read(
            row,
            *(await _segment_counts(db, row)),
        )
        for row in rows
    ]


@admin_crm_router.post("/segments", response_model=AdminCustomerSegmentRead, status_code=status.HTTP_201_CREATED)
async def create_segment(
    payload: AdminCustomerSegmentPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("segments.manage", write=True)),
) -> AdminCustomerSegmentRead:
    try:
        filters_json = normalize_segment_filters(payload.filters_json)
    except (ValidationError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    segment = AdminCustomerSegment(owner_user_id=context.user.id, name=payload.name.strip(), filters_json=filters_json, is_shared=payload.is_shared, segment_type=payload.segment_type)
    db.add(segment)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Segment name already exists") from None
    await _record_segment_history(db, segment=segment, context=context, action="create", before=None, after=_segment_snapshot(segment))
    await add_admin_audit(db, request, context, action="segment.create", entity_type="segment", entity_id=segment.id, after={"name": segment.name, "filters": filters_json, "segment_type": segment.segment_type})
    await db.commit()
    segment = await _get_visible_segment(db, context, segment.id)
    return _segment_read(
        segment,
        *(await _segment_counts(db, segment)),
    )


@admin_crm_router.put("/segments/{segment_id}", response_model=AdminCustomerSegmentRead)
async def update_segment(
    segment_id: int,
    payload: AdminCustomerSegmentUpdatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("segments.manage", write=True)),
) -> AdminCustomerSegmentRead:
    segment = await _get_visible_segment(db, context, segment_id)
    if segment.owner_user_id != context.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    ensure_not_stale(actual=segment.updated_at, expected=payload.expected_updated_at)
    try:
        filters_json = normalize_segment_filters(payload.filters_json)
    except (ValidationError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    before = _segment_snapshot(segment)
    segment.name = payload.name.strip()
    segment.filters_json = filters_json
    segment.is_shared = payload.is_shared
    if segment.segment_type != payload.segment_type:
        segment.segment_type = payload.segment_type
        if payload.segment_type == "dynamic":
            await db.execute(delete(AdminCustomerSegmentSnapshotItem).where(AdminCustomerSegmentSnapshotItem.segment_id == segment.id))
            segment.snapshot_count = 0
            segment.snapshot_version = 0
            segment.snapshot_at = None
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Segment name already exists") from None
    after = _segment_snapshot(segment)
    await _record_segment_history(db, segment=segment, context=context, action="update", before=before, after=after)
    await add_admin_audit(db, request, context, action="segment.update", entity_type="segment", entity_id=segment.id, before=before, after=after)
    await db.commit()
    segment = await _get_visible_segment(db, context, segment.id)
    return _segment_read(
        segment,
        *(await _segment_counts(db, segment)),
    )


@admin_crm_router.post("/segments/{segment_id}/snapshot", response_model=AdminCustomerSegmentSnapshotRead)
async def snapshot_segment(
    segment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("segments.manage", write=True)),
) -> AdminCustomerSegmentSnapshotRead:
    segment = await _get_visible_segment(db, context, segment_id)
    if segment.owner_user_id != context.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    before = _segment_snapshot(segment)
    ids = await list_audience_ids(db, segment.filters_json, limit=MAX_SEGMENT_EXPORT)
    await db.execute(delete(AdminCustomerSegmentSnapshotItem).where(AdminCustomerSegmentSnapshotItem.segment_id == segment.id))
    next_version = segment.snapshot_version + 1
    for user_id in ids:
        db.add(AdminCustomerSegmentSnapshotItem(segment_id=segment.id, user_id=user_id, snapshot_version=next_version))
    now = ufa_now()
    segment.segment_type = "static"
    segment.snapshot_version = next_version
    segment.snapshot_at = now
    segment.snapshot_count = len(ids)
    await db.flush()
    after = _segment_snapshot(segment)
    await _record_segment_history(db, segment=segment, context=context, action="snapshot", before=before, after=after, metadata={"count": len(ids), "truncated": len(ids) >= MAX_SEGMENT_EXPORT})
    await add_admin_audit(db, request, context, action="segment.snapshot", entity_type="segment", entity_id=segment.id, before=before, after=after)
    await db.commit()
    return AdminCustomerSegmentSnapshotRead(segment_id=segment.id, snapshot_version=segment.snapshot_version, snapshot_count=segment.snapshot_count, snapshot_at=segment.snapshot_at or now)


@admin_crm_router.get("/segments/{segment_id}/customers", response_model=AdminPage[AdminAudienceSample])
async def segment_customers(
    segment_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("segments.read")),
) -> AdminPage[AdminAudienceSample]:
    segment = await _get_visible_segment(db, context, segment_id)
    count, _ = await _segment_counts(db, segment)
    statement = build_static_segment_query(segment.id) if segment.segment_type == "static" else build_audience_query(segment.filters_json)
    rows = (await db.execute(statement.order_by(User.created_at.desc()).offset(offset).limit(limit))).all()
    return AdminPage(
        items=[AdminAudienceSample(
            id=user.id,
            name=user.name,
            surname=user.surname,
            email=user.email,
            phone_number=user.phone_number,
            orders_count=int(orders_count or 0),
            paid_total=paid_total or 0,
            last_order_at=last_order_at,
        ) for user, orders_count, paid_total, last_order_at in rows],
        total=count,
        limit=limit,
        offset=offset,
    )


@admin_crm_router.get("/segments/{segment_id}/history", response_model=list[AdminCustomerSegmentHistoryRead])
async def segment_history(
    segment_id: int,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("segments.read")),
) -> list[AdminCustomerSegmentHistoryRead]:
    await _get_visible_segment(db, context, segment_id)
    rows = list((await db.execute(
        select(AdminCustomerSegmentHistory)
        .options(joinedload(AdminCustomerSegmentHistory.actor).joinedload(Admin.user))
        .where(AdminCustomerSegmentHistory.segment_id == segment_id)
        .order_by(AdminCustomerSegmentHistory.created_at.desc(), AdminCustomerSegmentHistory.id.desc())
    )).scalars().all())
    return [_segment_history_read(row) for row in rows]


@admin_crm_router.get("/segments/{segment_id}/export.csv")
async def export_segment_csv(
    segment_id: int,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("segments.read")),
) -> StreamingResponse:
    segment = await _get_visible_segment(db, context, segment_id)
    statement = build_static_segment_query(segment.id) if segment.segment_type == "static" else build_audience_query(segment.filters_json)
    rows = (await db.execute(statement.order_by(User.id).limit(MAX_SEGMENT_EXPORT))).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "surname", "email", "phone", "orders_count", "paid_total", "last_order_at"])
    for user, orders_count, paid_total, last_order_at in rows:
        writer.writerow([user.id, user.name, user.surname, user.email or "", user.phone_number or "", int(orders_count or 0), paid_total or 0, last_order_at.isoformat() if last_order_at else ""])
    data = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        iter((data,)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="segment-{segment.id}.csv"'},
    )


@admin_crm_router.delete("/segments/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    segment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("segments.manage", write=True)),
) -> None:
    segment = await _get_visible_segment(db, context, segment_id)
    if segment.owner_user_id != context.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    in_use = (await db.execute(select(AdminPushCampaign.id).where(AdminPushCampaign.segment_id == segment_id).limit(1))).scalar_one_or_none()
    if in_use is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Segment is used by a campaign")
    await add_admin_audit(db, request, context, action="segment.delete", entity_type="segment", entity_id=segment.id, before=_segment_snapshot(segment))
    await db.delete(segment)
    await db.commit()
