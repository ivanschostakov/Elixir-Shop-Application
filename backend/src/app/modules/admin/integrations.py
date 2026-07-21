import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import (
    AMOCRM_ACCESS_TOKEN,
    ADMIN_JOB_QUEUE_NAME,
    CDEK_ACCOUNT,
    CDEK_SECURE_PASSWORD,
    INTELLECTMONEY_BEARER_TOKEN,
    INTELLECTMONEY_SHOP_ID,
    MOY_SKLAD_TOKEN,
    TELEGRAM_BOT_TOKEN,
    YANDEX_DELIVERY_TOKEN,
)
from src.app.modules.admin.schemas import (
    AdminPage,
    IntegrationRetryPayload,
    IntegrationRunRead,
    IntegrationStatusRead,
)
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.app.services.cache import get_cache_service
from src.database import SessionLocal, get_db
from src.database.models import IntegrationRun
from src.integrations.moysklad import sync_moysklad_product_catalog

admin_integrations_router = APIRouter(prefix="/integrations", tags=["admin_integrations"])

PROVIDERS = (
    ("amocrm", "amoCRM", lambda: bool(AMOCRM_ACCESS_TOKEN)),
    ("moysklad", "МойСклад", lambda: bool(MOY_SKLAD_TOKEN)),
    ("intellectmoney", "IntellectMoney", lambda: bool(INTELLECTMONEY_BEARER_TOKEN and INTELLECTMONEY_SHOP_ID)),
    ("cdek", "CDEK", lambda: bool(CDEK_ACCOUNT and CDEK_SECURE_PASSWORD)),
    ("yandex_delivery", "Яндекс Доставка", lambda: bool(YANDEX_DELIVERY_TOKEN)),
    ("telegram", "Telegram", lambda: bool(TELEGRAM_BOT_TOKEN)),
)


async def _run_moysklad_catalog_sync(run_id: int) -> None:
    async with SessionLocal() as db:
        row = await db.get(IntegrationRun, run_id)
        if row is None or row.status not in {"queued", "running"}:
            return
        row.status = "running"
        row.attempts = max(row.attempts, 1)
        await db.commit()
    try:
        stats = await sync_moysklad_product_catalog()
    except Exception as error:
        async with SessionLocal() as db:
            row = await db.get(IntegrationRun, run_id)
            if row is not None:
                row.status = "error"
                row.error = str(error)[:8000]
                row.finished_at = datetime.now(timezone.utc)
                await db.commit()
        return
    async with SessionLocal() as db:
        row = await db.get(IntegrationRun, run_id)
        if row is not None:
            row.status = "success"
            row.counters_json = stats.as_dict()
            row.finished_at = datetime.now(timezone.utc)
            await db.commit()


@admin_integrations_router.get("", response_model=list[IntegrationStatusRead])
async def list_integrations(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("integrations.read")),
) -> list[IntegrationStatusRead]:
    result: list[IntegrationStatusRead] = []
    for provider, label, configured_fn in PROVIDERS:
        configured = configured_fn()
        latest = (await db.execute(select(IntegrationRun).where(IntegrationRun.provider == provider).order_by(IntegrationRun.started_at.desc(), IntegrationRun.id.desc()).limit(1))).scalar_one_or_none()
        if not configured:
            state = "disabled"
        elif latest is not None and latest.status == "error":
            state = "error"
        elif latest is not None and latest.status in {"queued", "running"}:
            state = "warning"
        else:
            state = "healthy"
        result.append(IntegrationStatusRead(
            provider=provider,
            label=label,
            configured=configured,
            status=state,
            last_run_at=latest.started_at if latest else None,
            last_run_status=latest.status if latest else None,
            last_error=latest.error if latest else None,
        ))
    return result


@admin_integrations_router.get("/runs", response_model=AdminPage[IntegrationRunRead])
async def list_integration_runs(
    provider: str | None = Query(default=None, max_length=80),
    run_status: str | None = Query(default=None, alias="status", max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("integrations.read")),
) -> AdminPage[IntegrationRunRead]:
    filters = []
    if provider:
        filters.append(IntegrationRun.provider == provider)
    if run_status:
        filters.append(IntegrationRun.status == run_status)
    total = int((await db.execute(select(func.count(IntegrationRun.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(select(IntegrationRun).where(*filters).order_by(IntegrationRun.started_at.desc(), IntegrationRun.id.desc()).offset(offset).limit(limit))).scalars().all())
    return AdminPage(items=[IntegrationRunRead.model_validate(row) for row in rows], total=total, limit=limit, offset=offset)


@admin_integrations_router.post("/{provider}/retry", response_model=IntegrationRunRead, status_code=status.HTTP_202_ACCEPTED)
async def retry_integration(
    provider: str,
    payload: IntegrationRetryPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("integrations.retry", write=True)),
) -> IntegrationRunRead:
    existing = (await db.execute(select(IntegrationRun).where(IntegrationRun.idempotency_key == payload.idempotency_key))).scalar_one_or_none()
    if existing is not None:
        return IntegrationRunRead.model_validate(existing)
    if provider != "moysklad" or payload.operation != "catalog_sync":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="This integration operation cannot be retried from the admin panel")
    if not MOY_SKLAD_TOKEN:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MoySklad is not configured")
    run = IntegrationRun(
        provider=provider,
        operation=payload.operation,
        status="queued",
        requested_by_user_id=context.user.id,
        idempotency_key=payload.idempotency_key,
    )
    db.add(run)
    await db.flush()
    await add_admin_audit(db, request, context, action="integration.retry", entity_type="integration_run", entity_id=run.id, after={"provider": provider, "operation": payload.operation})
    await db.commit()
    await db.refresh(run)
    redis = get_cache_service().client
    if redis is None:
        run.status = "error"
        run.error = "Redis admin job queue is unavailable"
        run.finished_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin job queue is unavailable")
    try:
        await redis.rpush(ADMIN_JOB_QUEUE_NAME, json.dumps({"type": "moysklad_catalog_sync", "run_id": run.id}))
    except Exception as error:
        run.status = "error"
        run.error = f"Failed to enqueue admin job: {error}"[:8000]
        run.finished_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to enqueue admin job") from error
    return IntegrationRunRead.model_validate(run)
