from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette import status

from config import ufa_now
from src.app.modules.admin.helpers import ensure_not_stale
from src.app.modules.admin.schemas import (
    AdminAlertPage,
    AdminAlertRead,
    AdminAutomationRunPayload,
    AdminOrderAutomationExecutionRead,
    AdminOrderAutomationPresetApplyResponse,
    AdminOrderAutomationPresetRead,
    AdminOrderAutomationPreviewItem,
    AdminOrderAutomationPreviewRead,
    AdminOrderAutomationRulePayload,
    AdminOrderAutomationRuleRead,
    AdminOrderAutomationRuleUpdatePayload,
    AdminPage,
    AdminSlaPolicyRead,
    AdminSlaPolicyUpdatePayload,
    AdminSlaSummaryItem,
    IntegrationRunRead,
)
from src.app.services.admin import AdminContext, add_admin_audit, default_max_attempts, enqueue_integration_run, require_permission
from src.app.services.admin.alerts import resolve_admin_alert
from src.app.services.admin.automation import (
    default_order_automation_presets,
    normalize_order_rule_action,
    normalize_order_rule_conditions,
    preset_rule_name,
    preview_order_automation_conditions,
)
from src.database import get_db
from src.database.models import (
    Admin,
    AdminAlert,
    AdminAlertReadReceipt,
    AdminOrderAutomationExecution,
    AdminOrderAutomationRule,
    AdminSlaPolicy,
    AdminTask,
    IntegrationRun,
    Order,
)
from src.database.models.orders.history import get_order_status_code


admin_automation_router = APIRouter(tags=["admin_automation"])


def _admin_name(admin: Admin | None) -> str | None:
    return f"{admin.user.name} {admin.user.surname}".strip() if admin else None


async def _normalize_rule_payload(db: AsyncSession, payload: AdminOrderAutomationRulePayload) -> tuple[dict, dict]:
    try:
        conditions = normalize_order_rule_conditions(payload.conditions_json)
        action = normalize_order_rule_action(payload.action_json)
    except (ValidationError, ValueError) as error:
        detail = error.errors() if isinstance(error, ValidationError) else str(error)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from error
    if action["kind"] == "create_task":
        assignee = await db.get(Admin, int(action["assignee_user_id"]))
        if assignee is None or not assignee.is_active:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Automation assignee is unavailable")
    return conditions, action


async def _get_rule(db: AsyncSession, rule_id: int) -> AdminOrderAutomationRule:
    row = (await db.execute(
        select(AdminOrderAutomationRule)
        .options(joinedload(AdminOrderAutomationRule.created_by).joinedload(Admin.user))
        .where(AdminOrderAutomationRule.id == rule_id)
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation rule not found")
    return row


async def _rule_read(db: AsyncSession, row: AdminOrderAutomationRule) -> AdminOrderAutomationRuleRead:
    executions_count = int((await db.execute(select(func.count(AdminOrderAutomationExecution.id)).where(
        AdminOrderAutomationExecution.rule_id == row.id
    ))).scalar_one())
    return AdminOrderAutomationRuleRead(
        id=row.id,
        name=row.name,
        description=row.description,
        is_enabled=row.is_enabled,
        priority=row.priority,
        conditions_json=row.conditions_json,
        action_json=row.action_json,
        created_by_name=_admin_name(row.created_by),
        last_run_at=row.last_run_at,
        last_match_count=row.last_match_count,
        last_error=row.last_error,
        executions_count=executions_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _preset_read(db: AsyncSession, preset: dict) -> AdminOrderAutomationPresetRead:
    rule = (await db.execute(select(AdminOrderAutomationRule).where(AdminOrderAutomationRule.name == preset_rule_name(preset)))).scalar_one_or_none()
    return AdminOrderAutomationPresetRead(
        code=preset["code"],
        name_ru=preset["name_ru"],
        name_en=preset["name_en"],
        description_ru=preset["description_ru"],
        description_en=preset["description_en"],
        priority=preset["priority"],
        conditions_json=preset["conditions_json"],
        action_json=preset["action_json"],
        exists=rule is not None,
        rule_id=rule.id if rule else None,
    )


def _preview_item(order: Order) -> AdminOrderAutomationPreviewItem:
    customer = getattr(order, "user", None)
    customer_name = f"{getattr(customer, 'name', '')} {getattr(customer, 'surname', '')}".strip() or str(order.user_id)
    return AdminOrderAutomationPreviewItem(
        order_id=order.id,
        order_code=order.order_code,
        status_code=get_order_status_code(order),
        payment_status=order.payment_status,
        customer_name=customer_name,
        created_at=order.created_at,
    )


@admin_automation_router.get("/order-automation-rules", response_model=AdminPage[AdminOrderAutomationRuleRead])
async def list_order_automation_rules(
    enabled: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("automation.read")),
) -> AdminPage[AdminOrderAutomationRuleRead]:
    filters = [AdminOrderAutomationRule.is_enabled == enabled] if enabled is not None else []
    total = int((await db.execute(select(func.count(AdminOrderAutomationRule.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(
        select(AdminOrderAutomationRule)
        .options(joinedload(AdminOrderAutomationRule.created_by).joinedload(Admin.user))
        .where(*filters)
        .order_by(AdminOrderAutomationRule.priority, AdminOrderAutomationRule.id)
        .offset(offset)
        .limit(limit)
    )).scalars().all())
    return AdminPage(items=[await _rule_read(db, row) for row in rows], total=total, limit=limit, offset=offset)


@admin_automation_router.get("/order-automation-rules/presets", response_model=list[AdminOrderAutomationPresetRead])
async def list_order_automation_presets(
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("automation.read")),
) -> list[AdminOrderAutomationPresetRead]:
    presets = default_order_automation_presets(context.user.id)
    return [await _preset_read(db, preset) for preset in presets]


@admin_automation_router.post("/order-automation-rules/presets/apply", response_model=AdminOrderAutomationPresetApplyResponse, status_code=status.HTTP_201_CREATED)
async def apply_order_automation_presets(
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("automation.manage", write=True)),
) -> AdminOrderAutomationPresetApplyResponse:
    created = 0
    skipped = 0
    presets = default_order_automation_presets(context.user.id)
    for preset in presets:
        rule_name = preset_rule_name(preset)
        exists = (await db.execute(select(AdminOrderAutomationRule.id).where(AdminOrderAutomationRule.name == rule_name))).scalar_one_or_none()
        if exists is not None:
            skipped += 1
            continue
        row = AdminOrderAutomationRule(
            name=rule_name,
            description=preset["description"],
            is_enabled=False,
            priority=preset["priority"],
            conditions_json=normalize_order_rule_conditions(preset["conditions_json"]),
            action_json=normalize_order_rule_action(preset["action_json"]),
            created_by_user_id=context.user.id,
        )
        db.add(row)
        await db.flush()
        await add_admin_audit(
            db,
            request,
            context,
            action="order_automation.preset_create",
            entity_type="automation_rule",
            entity_id=row.id,
            after={"preset": preset["code"], "name": row.name, "is_enabled": row.is_enabled},
        )
        created += 1
    await db.commit()
    return AdminOrderAutomationPresetApplyResponse(
        created=created,
        skipped=skipped,
        items=[await _preset_read(db, preset) for preset in presets],
    )


@admin_automation_router.post("/order-automation-rules", response_model=AdminOrderAutomationRuleRead, status_code=status.HTTP_201_CREATED)
async def create_order_automation_rule(
    payload: AdminOrderAutomationRulePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("automation.manage", write=True)),
) -> AdminOrderAutomationRuleRead:
    if payload.is_enabled:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Create the rule disabled, review it, then enable it")
    conditions, action = await _normalize_rule_payload(db, payload)
    row = AdminOrderAutomationRule(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        is_enabled=False,
        priority=payload.priority,
        conditions_json=conditions,
        action_json=action,
        created_by_user_id=context.user.id,
    )
    db.add(row)
    await db.flush()
    await add_admin_audit(db, request, context, action="order_automation.create", entity_type="automation_rule", entity_id=row.id, after={"name": row.name, "conditions": conditions, "action": action})
    await db.commit()
    return await _rule_read(db, await _get_rule(db, row.id))


@admin_automation_router.put("/order-automation-rules/{rule_id}", response_model=AdminOrderAutomationRuleRead)
async def update_order_automation_rule(
    rule_id: int,
    payload: AdminOrderAutomationRuleUpdatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("automation.manage", write=True)),
) -> AdminOrderAutomationRuleRead:
    row = await _get_rule(db, rule_id)
    ensure_not_stale(actual=row.updated_at, expected=payload.expected_updated_at)
    conditions, action = await _normalize_rule_payload(db, payload)
    before = await _rule_read(db, row)
    row.name = payload.name.strip()
    row.description = payload.description.strip() if payload.description else None
    row.is_enabled = payload.is_enabled
    row.priority = payload.priority
    row.conditions_json = conditions
    row.action_json = action
    row.last_error = None
    await db.flush()
    result = await _rule_read(db, await _get_rule(db, row.id))
    await add_admin_audit(db, request, context, action="order_automation.update", entity_type="automation_rule", entity_id=row.id, before=before.model_dump(mode="json"), after=result.model_dump(mode="json"))
    await db.commit()
    return result


@admin_automation_router.get("/order-automation-rules/{rule_id}/preview", response_model=AdminOrderAutomationPreviewRead)
async def preview_order_automation_rule(
    rule_id: int,
    limit: int = Query(default=10, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("automation.read")),
) -> AdminOrderAutomationPreviewRead:
    row = await _get_rule(db, rule_id)
    matched, sample = await preview_order_automation_conditions(db, row.conditions_json, limit=limit)
    return AdminOrderAutomationPreviewRead(matched=matched, sample=[_preview_item(order) for order in sample])


@admin_automation_router.delete("/order-automation-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order_automation_rule(
    rule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("automation.manage", write=True)),
) -> None:
    row = await _get_rule(db, rule_id)
    if row.is_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Disable the rule before deleting it")
    await add_admin_audit(db, request, context, action="order_automation.delete", entity_type="automation_rule", entity_id=row.id, before={"name": row.name})
    await db.delete(row)
    await db.commit()


@admin_automation_router.post("/order-automation-rules/{rule_id}/run", response_model=IntegrationRunRead, status_code=status.HTTP_202_ACCEPTED)
async def run_order_automation_rule(
    rule_id: int,
    payload: AdminAutomationRunPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("automation.manage", write=True)),
) -> IntegrationRunRead:
    row = await _get_rule(db, rule_id)
    ensure_not_stale(actual=row.updated_at, expected=payload.expected_updated_at)
    existing = (await db.execute(select(IntegrationRun).where(IntegrationRun.idempotency_key == payload.idempotency_key))).scalar_one_or_none()
    if existing is not None:
        if existing.operation != "order_automation" or existing.target_id != str(rule_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key belongs to another operation")
        return IntegrationRunRead.model_validate(existing)
    run = IntegrationRun(
        provider="admin",
        operation="order_automation",
        status="queued",
        requested_by_user_id=context.user.id,
        target_type="automation_rule",
        target_id=str(rule_id),
        attempts=0,
        max_attempts=default_max_attempts(),
        input_json={"include_disabled": True},
        idempotency_key=payload.idempotency_key,
    )
    db.add(run)
    await db.flush()
    await add_admin_audit(db, request, context, action="order_automation.run", entity_type="automation_rule", entity_id=rule_id, after={"run_id": run.id})
    await db.commit()
    await db.refresh(run)
    try:
        await enqueue_integration_run(run.id)
    except Exception as error:
        run.status = "error"
        run.error = f"Failed to enqueue automation: {error}"[:8000]
        run.finished_at = ufa_now()
        await db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Automation queue is unavailable") from error
    return IntegrationRunRead.model_validate(run)


@admin_automation_router.get("/order-automation-rules/{rule_id}/executions", response_model=AdminPage[AdminOrderAutomationExecutionRead])
async def list_order_automation_executions(
    rule_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("automation.read")),
) -> AdminPage[AdminOrderAutomationExecutionRead]:
    if await db.get(AdminOrderAutomationRule, rule_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation rule not found")
    total = int((await db.execute(select(func.count(AdminOrderAutomationExecution.id)).where(AdminOrderAutomationExecution.rule_id == rule_id))).scalar_one())
    rows = (await db.execute(
        select(AdminOrderAutomationExecution, Order.order_code)
        .join(Order, Order.id == AdminOrderAutomationExecution.order_id)
        .where(AdminOrderAutomationExecution.rule_id == rule_id)
        .order_by(AdminOrderAutomationExecution.executed_at.desc(), AdminOrderAutomationExecution.id.desc())
        .offset(offset)
        .limit(limit)
    )).all()
    return AdminPage(items=[AdminOrderAutomationExecutionRead(
        id=row.id,
        rule_id=row.rule_id,
        order_id=row.order_id,
        order_code=order_code,
        action_kind=row.action_kind,
        status=row.status,
        result_json=row.result_json,
        error=row.error,
        executed_at=row.executed_at,
    ) for row, order_code in rows], total=total, limit=limit, offset=offset)


@admin_automation_router.get("/sla-policies", response_model=list[AdminSlaPolicyRead])
async def list_sla_policies(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("sla.read")),
) -> list[AdminSlaPolicyRead]:
    rows = list((await db.execute(select(AdminSlaPolicy).order_by(AdminSlaPolicy.resolution_minutes))).scalars().all())
    return [AdminSlaPolicyRead.model_validate(row, from_attributes=True) for row in rows]


@admin_automation_router.put("/sla-policies/{policy_id}", response_model=AdminSlaPolicyRead)
async def update_sla_policy(
    policy_id: int,
    payload: AdminSlaPolicyUpdatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("sla.manage", write=True)),
) -> AdminSlaPolicyRead:
    row = await db.get(AdminSlaPolicy, policy_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SLA policy not found")
    ensure_not_stale(actual=row.updated_at, expected=payload.expected_updated_at)
    if payload.resolution_minutes < payload.response_minutes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Resolution time must not be shorter than response time")
    before = AdminSlaPolicyRead.model_validate(row, from_attributes=True).model_dump(mode="json")
    row.response_minutes = payload.response_minutes
    row.resolution_minutes = payload.resolution_minutes
    row.is_enabled = payload.is_enabled
    await db.flush()
    result = AdminSlaPolicyRead.model_validate(row, from_attributes=True)
    await add_admin_audit(db, request, context, action="sla_policy.update", entity_type="sla_policy", entity_id=row.id, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    return result


@admin_automation_router.get("/sla-summary", response_model=list[AdminSlaSummaryItem])
async def get_sla_summary(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("sla.read")),
) -> list[AdminSlaSummaryItem]:
    admins = list((await db.execute(
        select(Admin).options(joinedload(Admin.user)).where(Admin.is_active.is_(True)).order_by(Admin.user_id)
    )).scalars().all())
    cutoff = ufa_now() - timedelta(days=30)
    result: list[AdminSlaSummaryItem] = []
    for admin in admins:
        open_tasks = int((await db.execute(select(func.count(AdminTask.id)).where(
            AdminTask.assignee_user_id == admin.user_id,
            AdminTask.status.in_(("open", "in_progress")),
        ))).scalar_one())
        breached_tasks = int((await db.execute(select(func.count(AdminTask.id)).where(
            AdminTask.assignee_user_id == admin.user_id,
            AdminTask.status.in_(("open", "in_progress")),
            AdminTask.sla_breached_at.is_not(None),
        ))).scalar_one())
        completed_30d = int((await db.execute(select(func.count(AdminTask.id)).where(
            AdminTask.assignee_user_id == admin.user_id,
            AdminTask.status == "done",
            AdminTask.completed_at >= cutoff,
            AdminTask.resolution_due_at.is_not(None),
        ))).scalar_one())
        on_time_30d = int((await db.execute(select(func.count(AdminTask.id)).where(
            AdminTask.assignee_user_id == admin.user_id,
            AdminTask.status == "done",
            AdminTask.completed_at >= cutoff,
            AdminTask.completed_at <= AdminTask.resolution_due_at,
        ))).scalar_one())
        compliance = (Decimal(on_time_30d) / Decimal(completed_30d) * 100).quantize(Decimal("0.1")) if completed_30d else Decimal("100.0")
        result.append(AdminSlaSummaryItem(
            assignee_user_id=admin.user_id,
            assignee_name=_admin_name(admin) or str(admin.user_id),
            open_tasks=open_tasks,
            breached_tasks=breached_tasks,
            completed_30d=completed_30d,
            on_time_30d=on_time_30d,
            compliance_percent=compliance,
        ))
    return result


def _alert_read(row: AdminAlert, *, is_read: bool) -> AdminAlertRead:
    return AdminAlertRead(
        id=row.id,
        severity=row.severity,
        source=row.source,
        code=row.code,
        title_ru=row.title_ru,
        title_en=row.title_en,
        message=row.message,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        path=row.path,
        occurrence_count=row.occurrence_count,
        is_read=is_read,
        last_occurred_at=row.last_occurred_at,
        resolved_at=row.resolved_at,
        created_at=row.created_at,
    )


@admin_automation_router.get("/alerts", response_model=AdminAlertPage)
async def list_alerts(
    include_resolved: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("alerts.read")),
) -> AdminAlertPage:
    filters = [] if include_resolved else [AdminAlert.resolved_at.is_(None)]
    receipt_exists = select(AdminAlertReadReceipt.id).where(
        AdminAlertReadReceipt.alert_id == AdminAlert.id,
        AdminAlertReadReceipt.admin_user_id == context.user.id,
    ).exists()
    total = int((await db.execute(select(func.count(AdminAlert.id)).where(*filters))).scalar_one())
    unread_count = int((await db.execute(select(func.count(AdminAlert.id)).where(*filters, ~receipt_exists))).scalar_one())
    rows = (await db.execute(
        select(AdminAlert, receipt_exists.label("is_read"))
        .where(*filters)
        .order_by(AdminAlert.resolved_at.is_not(None), AdminAlert.last_occurred_at.desc())
        .limit(limit)
    )).all()
    return AdminAlertPage(items=[_alert_read(row, is_read=bool(is_read)) for row, is_read in rows], unread_count=unread_count, total=total)


@admin_automation_router.post("/alerts/{alert_id}/read", response_model=AdminAlertRead)
async def mark_alert_read(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("alerts.read", write=True)),
) -> AdminAlertRead:
    row = await db.get(AdminAlert, alert_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    receipt = (await db.execute(select(AdminAlertReadReceipt).where(
        AdminAlertReadReceipt.alert_id == alert_id,
        AdminAlertReadReceipt.admin_user_id == context.user.id,
    ))).scalar_one_or_none()
    if receipt is None:
        db.add(AdminAlertReadReceipt(alert_id=alert_id, admin_user_id=context.user.id))
        await db.commit()
    return _alert_read(row, is_read=True)


@admin_automation_router.post("/alerts/{alert_id}/resolve", response_model=AdminAlertRead)
async def resolve_alert(
    alert_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("alerts.manage", write=True)),
) -> AdminAlertRead:
    row = await db.get(AdminAlert, alert_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    await resolve_admin_alert(db, fingerprint=row.fingerprint, resolved_by_user_id=context.user.id)
    await add_admin_audit(db, request, context, action="alert.resolve", entity_type="alert", entity_id=row.id, after={"fingerprint": row.fingerprint})
    await db.commit()
    await db.refresh(row)
    return _alert_read(row, is_read=True)
