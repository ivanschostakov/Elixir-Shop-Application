from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette import status

from src.app.modules.admin.helpers import ensure_not_stale
from src.app.modules.admin.schemas import (
    AdminMarketingAutomationRead,
    AdminMarketingAutomationUpdatePayload,
    AdminPage,
    AdminPushCampaignControlPayload,
    AdminPushCampaignLaunchPayload,
    AdminPushCampaignMetricsRead,
    AdminPushCampaignPayload,
    AdminPushCampaignPreviewPayload,
    AdminPushCampaignPreviewRead,
    AdminPushCampaignRead,
    AdminPushCampaignRecipientRead,
    AdminPushCampaignTemplateRead,
    AdminPushCampaignUpdatePayload,
    IntegrationRunRead,
)
from src.app.services.admin import AdminContext, add_admin_audit, default_max_attempts, enqueue_integration_run, require_permission
from src.app.services.admin.audiences import MAX_CAMPAIGN_AUDIENCE, count_segment_audience, list_segment_audience_ids
from src.app.services.notifications.core import normalize_marketing_automation_settings
from src.database import get_db
from src.database.models import (
    AdminCustomerSegment,
    AdminMarketingAutomation,
    AdminPushCampaign,
    AdminPushCampaignRecipient,
    AdminPushCampaignTemplate,
    IntegrationRun,
    User,
)

admin_campaigns_router = APIRouter(tags=["admin_campaigns"])


def _normalize_deep_link(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized.startswith("/") or normalized.startswith("//"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Deep link must be an internal app path")
    return normalized


def _normalize_goal(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def _normalize_utm(value: dict[str, object] | None) -> dict[str, str]:
    if not value:
        return {}
    normalized: dict[str, str] = {}
    for key, raw in value.items():
        clean_key = str(key).strip().lower()
        if clean_key not in {"source", "medium", "campaign", "content", "term"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported UTM key: {key}")
        clean_value = str(raw).strip()
        if clean_value:
            normalized[clean_key] = clean_value[:160]
    return normalized


def _rate(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal("0.00")
    return (Decimal(numerator) * Decimal("100") / Decimal(denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _campaign_read(campaign: AdminPushCampaign) -> AdminPushCampaignRead:
    opened_count = len([recipient for recipient in campaign.recipients if recipient.opened_at is not None]) if "recipients" in campaign.__dict__ else 0
    clicked_count = len([recipient for recipient in campaign.recipients if recipient.clicked_at is not None]) if "recipients" in campaign.__dict__ else 0
    return AdminPushCampaignRead(
        id=campaign.id,
        name=campaign.name,
        title=campaign.title,
        body=campaign.body,
        deep_link=campaign.deep_link,
        template_id=campaign.template_id,
        template_name=campaign.template.name_ru if campaign.template else None,
        goal=campaign.goal,
        utm_json=campaign.utm_json or {},
        status=campaign.status,
        segment_id=campaign.segment_id,
        segment_name=campaign.segment.name if campaign.segment else None,
        audience_count=campaign.audience_count,
        sent_count=campaign.sent_count,
        skipped_count=campaign.skipped_count,
        failed_count=campaign.failed_count,
        opened_count=opened_count,
        clicked_count=clicked_count,
        delivery_rate=_rate(campaign.sent_count, campaign.audience_count),
        click_rate=_rate(clicked_count, campaign.sent_count),
        scheduled_at=campaign.scheduled_at,
        started_at=campaign.started_at,
        finished_at=campaign.finished_at,
        error=campaign.error,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


async def _get_campaign(db: AsyncSession, campaign_id: int) -> AdminPushCampaign:
    campaign = (await db.execute(
        select(AdminPushCampaign)
        .options(joinedload(AdminPushCampaign.segment), joinedload(AdminPushCampaign.template))
        .where(AdminPushCampaign.id == campaign_id)
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


async def _get_visible_segment(db: AsyncSession, context: AdminContext, segment_id: int) -> AdminCustomerSegment:
    segment = (await db.execute(select(AdminCustomerSegment).where(
        AdminCustomerSegment.id == segment_id,
        or_(AdminCustomerSegment.owner_user_id == context.user.id, AdminCustomerSegment.is_shared.is_(True)),
    ))).scalar_one_or_none()
    if segment is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Segment not found")
    return segment


async def _get_active_template(db: AsyncSession, template_id: int | None) -> AdminPushCampaignTemplate | None:
    if template_id is None:
        return None
    template = await db.get(AdminPushCampaignTemplate, template_id)
    if template is None or not template.is_active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Campaign template not found")
    return template


async def _campaign_metrics(db: AsyncSession, campaign: AdminPushCampaign) -> AdminPushCampaignMetricsRead:
    status_rows = (await db.execute(
        select(AdminPushCampaignRecipient.status, func.count(AdminPushCampaignRecipient.id))
        .where(AdminPushCampaignRecipient.campaign_id == campaign.id)
        .group_by(AdminPushCampaignRecipient.status)
    )).all()
    status_counts = {str(row_status): int(count) for row_status, count in status_rows}
    opened_count = int((await db.execute(select(func.count(AdminPushCampaignRecipient.id)).where(
        AdminPushCampaignRecipient.campaign_id == campaign.id,
        AdminPushCampaignRecipient.opened_at.is_not(None),
    ))).scalar_one())
    clicked_count = int((await db.execute(select(func.count(AdminPushCampaignRecipient.id)).where(
        AdminPushCampaignRecipient.campaign_id == campaign.id,
        AdminPushCampaignRecipient.clicked_at.is_not(None),
    ))).scalar_one())
    audience_count = campaign.audience_count or sum(status_counts.values())
    sent_count = campaign.sent_count or status_counts.get("sent", 0)
    failed_count = campaign.failed_count or status_counts.get("error", 0)
    skipped_count = campaign.skipped_count or status_counts.get("skipped", 0)
    pending_count = status_counts.get("pending", 0)
    return AdminPushCampaignMetricsRead(
        campaign_id=campaign.id,
        audience_count=audience_count,
        sent_count=sent_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        opened_count=opened_count,
        clicked_count=clicked_count,
        pending_count=pending_count,
        delivery_rate=_rate(sent_count, audience_count),
        click_rate=_rate(clicked_count, sent_count),
        failure_rate=_rate(failed_count, audience_count),
    )


@admin_campaigns_router.get("/campaign-templates", response_model=list[AdminPushCampaignTemplateRead])
async def list_campaign_templates(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("campaigns.read")),
) -> list[AdminPushCampaignTemplateRead]:
    rows = list((await db.execute(
        select(AdminPushCampaignTemplate)
        .where(AdminPushCampaignTemplate.is_active.is_(True))
        .order_by(AdminPushCampaignTemplate.category, AdminPushCampaignTemplate.id)
    )).scalars().all())
    return [AdminPushCampaignTemplateRead.model_validate(row, from_attributes=True) for row in rows]


@admin_campaigns_router.post("/campaigns/preview", response_model=AdminPushCampaignPreviewRead)
async def preview_campaign(
    payload: AdminPushCampaignPreviewPayload,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("campaigns.read")),
) -> AdminPushCampaignPreviewRead:
    segment = await _get_visible_segment(db, context, payload.segment_id)
    await _get_active_template(db, payload.template_id)
    audience_count = await count_segment_audience(db, segment, require_active=True)
    push_reachable_count = await count_segment_audience(db, segment, require_push=True, require_active=True)
    warnings: list[str] = []
    if push_reachable_count == 0:
        warnings.append("В сегменте нет клиентов с push-токеном" if payload.locale == "ru" else "No push-reachable customers in this segment")
    if audience_count != push_reachable_count:
        warnings.append(
            f"Push получат {push_reachable_count} из {audience_count} клиентов" if payload.locale == "ru"
            else f"{push_reachable_count} of {audience_count} customers are push-reachable"
        )
    return AdminPushCampaignPreviewRead(
        title=payload.title.strip(),
        body=payload.body.strip(),
        deep_link=_normalize_deep_link(payload.deep_link),
        segment_id=segment.id,
        segment_name=segment.name,
        audience_count=audience_count,
        push_reachable_count=push_reachable_count,
        estimated_send_count=push_reachable_count,
        warnings=warnings,
    )


@admin_campaigns_router.get("/campaigns", response_model=AdminPage[AdminPushCampaignRead])
async def list_campaigns(
    campaign_status: str | None = Query(default=None, alias="status", max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("campaigns.read")),
) -> AdminPage[AdminPushCampaignRead]:
    filters = [AdminPushCampaign.status == campaign_status] if campaign_status else []
    total = int((await db.execute(select(func.count(AdminPushCampaign.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(
        select(AdminPushCampaign)
        .options(joinedload(AdminPushCampaign.segment), joinedload(AdminPushCampaign.template))
        .where(*filters)
        .order_by(AdminPushCampaign.created_at.desc(), AdminPushCampaign.id.desc())
        .offset(offset)
        .limit(limit)
    )).scalars().all())
    return AdminPage(items=[_campaign_read(row) for row in rows], total=total, limit=limit, offset=offset)


@admin_campaigns_router.post("/campaigns", response_model=AdminPushCampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: AdminPushCampaignPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("campaigns.manage", write=True)),
) -> AdminPushCampaignRead:
    await _get_visible_segment(db, context, payload.segment_id)
    await _get_active_template(db, payload.template_id)
    campaign = AdminPushCampaign(
        **payload.model_dump(exclude={"name", "title", "body", "deep_link", "goal", "utm_json"}),
        name=payload.name.strip(),
        title=payload.title.strip(),
        body=payload.body.strip(),
        deep_link=_normalize_deep_link(payload.deep_link),
        goal=_normalize_goal(payload.goal),
        utm_json=_normalize_utm(payload.utm_json),
        created_by_user_id=context.user.id,
    )
    db.add(campaign)
    await db.flush()
    await add_admin_audit(db, request, context, action="campaign.create", entity_type="campaign", entity_id=campaign.id, after={"name": campaign.name, "segment_id": campaign.segment_id})
    await db.commit()
    return _campaign_read(await _get_campaign(db, campaign.id))


@admin_campaigns_router.put("/campaigns/{campaign_id}", response_model=AdminPushCampaignRead)
async def update_campaign(
    campaign_id: int,
    payload: AdminPushCampaignUpdatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("campaigns.manage", write=True)),
) -> AdminPushCampaignRead:
    campaign = await _get_campaign(db, campaign_id)
    if campaign.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft campaigns can be edited")
    ensure_not_stale(actual=campaign.updated_at, expected=payload.expected_updated_at)
    await _get_visible_segment(db, context, payload.segment_id)
    await _get_active_template(db, payload.template_id)
    before = _campaign_read(campaign).model_dump(mode="json")
    campaign.name = payload.name.strip()
    campaign.title = payload.title.strip()
    campaign.body = payload.body.strip()
    campaign.deep_link = _normalize_deep_link(payload.deep_link)
    campaign.segment_id = payload.segment_id
    campaign.template_id = payload.template_id
    campaign.goal = _normalize_goal(payload.goal)
    campaign.utm_json = _normalize_utm(payload.utm_json)
    await db.flush()
    result = _campaign_read(await _get_campaign(db, campaign.id))
    await add_admin_audit(db, request, context, action="campaign.update", entity_type="campaign", entity_id=campaign.id, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    return result


@admin_campaigns_router.post("/campaigns/{campaign_id}/launch", response_model=IntegrationRunRead, status_code=status.HTTP_202_ACCEPTED)
async def launch_campaign(
    campaign_id: int,
    payload: AdminPushCampaignLaunchPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("campaigns.send", write=True)),
) -> IntegrationRunRead:
    campaign = await _get_campaign(db, campaign_id)
    if campaign.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign is not a draft")
    ensure_not_stale(actual=campaign.updated_at, expected=payload.expected_updated_at)
    if campaign.segment is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign segment no longer exists")
    await _get_visible_segment(db, context, campaign.segment.id)
    existing = (await db.execute(select(IntegrationRun).where(IntegrationRun.idempotency_key == payload.idempotency_key))).scalar_one_or_none()
    if existing is not None:
        if existing.provider != "admin" or existing.operation != "push_campaign" or existing.target_id != str(campaign.id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key belongs to another operation")
        return IntegrationRunRead.model_validate(existing)

    current_count = await count_segment_audience(db, campaign.segment, require_push=True, require_active=True)
    if current_count != payload.expected_audience_count:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "audience_changed", "actual_count": current_count})
    recipient_ids = await list_segment_audience_ids(db, campaign.segment, require_push=True, require_active=True)
    if len(recipient_ids) > MAX_CAMPAIGN_AUDIENCE:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Campaign audience exceeds {MAX_CAMPAIGN_AUDIENCE}")
    if not recipient_ids:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign audience is empty")
    if len(recipient_ids) != payload.expected_audience_count:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "audience_changed", "actual_count": len(recipient_ids)})

    db.add_all([AdminPushCampaignRecipient(campaign_id=campaign.id, user_id=user_id) for user_id in recipient_ids])
    now = datetime.now(timezone.utc)
    if payload.scheduled_at is not None and payload.scheduled_at.tzinfo is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Scheduled time must include a timezone")
    scheduled_at = payload.scheduled_at if payload.scheduled_at and payload.scheduled_at > now else None
    campaign.status = "scheduled" if scheduled_at else "queued"
    campaign.scheduled_at = scheduled_at
    campaign.audience_count = len(recipient_ids)
    run = IntegrationRun(
        provider="admin",
        operation="push_campaign",
        status="queued",
        requested_by_user_id=context.user.id,
        target_type="campaign",
        target_id=str(campaign.id),
        attempts=0,
        max_attempts=default_max_attempts(),
        input_json={"campaign_id": campaign.id},
        next_attempt_at=scheduled_at,
        idempotency_key=payload.idempotency_key,
    )
    db.add(run)
    await db.flush()
    await add_admin_audit(
        db,
        request,
        context,
        action="campaign.launch",
        entity_type="campaign",
        entity_id=campaign.id,
        after={"run_id": run.id, "audience_count": len(recipient_ids), "scheduled_at": scheduled_at},
    )
    await db.commit()
    await db.refresh(run)
    delay_seconds = max(0, int((scheduled_at - now).total_seconds())) if scheduled_at else 0
    try:
        await enqueue_integration_run(run.id, delay_seconds=delay_seconds)
    except Exception as error:
        run.status = "error"
        run.error = f"Failed to enqueue push campaign: {error}"[:8000]
        run.finished_at = datetime.now(timezone.utc)
        campaign = await db.get(AdminPushCampaign, campaign.id)
        if campaign is not None:
            campaign.status = "failed"
            campaign.error = run.error
        await db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Campaign queue is unavailable") from error
    return IntegrationRunRead.model_validate(run)


@admin_campaigns_router.post("/campaigns/{campaign_id}/cancel", response_model=AdminPushCampaignRead)
async def cancel_campaign(
    campaign_id: int,
    payload: AdminPushCampaignControlPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("campaigns.send", write=True)),
) -> AdminPushCampaignRead:
    campaign = await _get_campaign(db, campaign_id)
    if campaign.status not in {"draft", "scheduled", "queued"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign can no longer be canceled")
    ensure_not_stale(actual=campaign.updated_at, expected=payload.expected_updated_at)
    campaign.status = "canceled"
    campaign.finished_at = datetime.now(timezone.utc)
    runs = list((await db.execute(select(IntegrationRun).where(
        IntegrationRun.target_type == "campaign",
        IntegrationRun.target_id == str(campaign.id),
        IntegrationRun.status.in_(("queued", "retrying")),
    ))).scalars().all())
    for run in runs:
        run.status = "canceled"
        run.finished_at = campaign.finished_at
    await add_admin_audit(db, request, context, action="campaign.cancel", entity_type="campaign", entity_id=campaign.id, after={"canceled_runs": [run.id for run in runs]})
    await db.commit()
    return _campaign_read(await _get_campaign(db, campaign.id))


@admin_campaigns_router.get("/campaigns/{campaign_id}/metrics", response_model=AdminPushCampaignMetricsRead)
async def campaign_metrics(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("campaigns.read")),
) -> AdminPushCampaignMetricsRead:
    campaign = await _get_campaign(db, campaign_id)
    return await _campaign_metrics(db, campaign)


@admin_campaigns_router.get("/campaigns/{campaign_id}/recipients", response_model=AdminPage[AdminPushCampaignRecipientRead])
async def campaign_recipients(
    campaign_id: int,
    recipient_status: str | None = Query(default=None, alias="status", max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("campaigns.read")),
) -> AdminPage[AdminPushCampaignRecipientRead]:
    await _get_campaign(db, campaign_id)
    filters = [AdminPushCampaignRecipient.campaign_id == campaign_id]
    if recipient_status:
        filters.append(AdminPushCampaignRecipient.status == recipient_status)
    total = int((await db.execute(select(func.count(AdminPushCampaignRecipient.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(
        select(AdminPushCampaignRecipient, User)
        .join(User, User.id == AdminPushCampaignRecipient.user_id)
        .where(*filters)
        .order_by(AdminPushCampaignRecipient.id.desc())
        .offset(offset)
        .limit(limit)
    )).all())
    items = [
        AdminPushCampaignRecipientRead(
            id=recipient.id,
            user_id=recipient.user_id,
            customer_name=f"{user.name} {user.surname}".strip() or f"User {user.id}",
            customer_email=user.email,
            status=recipient.status,
            attempts=recipient.attempts,
            error=recipient.error,
            sent_at=recipient.sent_at,
            opened_at=recipient.opened_at,
            clicked_at=recipient.clicked_at,
        )
        for recipient, user in rows
    ]
    return AdminPage(items=items, total=total, limit=limit, offset=offset)


def _automation_read(row: AdminMarketingAutomation) -> AdminMarketingAutomationRead:
    return AdminMarketingAutomationRead(
        id=row.id,
        code=row.code,
        name_ru=row.name_ru,
        name_en=row.name_en,
        is_enabled=row.is_enabled,
        settings_json=normalize_marketing_automation_settings(row.code, row.settings_json),
        last_run_at=row.last_run_at,
        last_result_json=row.last_result_json,
        last_error=row.last_error,
        updated_at=row.updated_at,
    )


@admin_campaigns_router.get("/automations", response_model=list[AdminMarketingAutomationRead])
async def list_automations(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("campaigns.read")),
) -> list[AdminMarketingAutomationRead]:
    rows = list((await db.execute(select(AdminMarketingAutomation).order_by(AdminMarketingAutomation.id))).scalars().all())
    return [_automation_read(row) for row in rows]


@admin_campaigns_router.patch("/automations/{automation_id}", response_model=AdminMarketingAutomationRead)
async def update_automation(
    automation_id: int,
    payload: AdminMarketingAutomationUpdatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("campaigns.manage", write=True)),
) -> AdminMarketingAutomationRead:
    row = await db.get(AdminMarketingAutomation, automation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
    ensure_not_stale(actual=row.updated_at, expected=payload.expected_updated_at)
    try:
        settings_json = normalize_marketing_automation_settings(row.code, payload.settings_json)
    except (ValidationError, ValueError) as error:
        detail = error.errors() if isinstance(error, ValidationError) else str(error)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from error
    before = {"is_enabled": row.is_enabled, "settings_json": row.settings_json}
    row.is_enabled = payload.is_enabled
    row.settings_json = settings_json
    await db.flush()
    await add_admin_audit(db, request, context, action="automation.update", entity_type="automation", entity_id=row.id, before=before, after={"is_enabled": row.is_enabled, "settings_json": settings_json})
    await db.commit()
    await db.refresh(row)
    return _automation_read(row)
