import json

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import (
    AMOCRM_ACCESS_TOKEN,
    ADMIN_COOKIE_SECURE,
    ADMIN_BACKUP_STATUS_PATH,
    ADMIN_JOB_STALE_SECONDS,
    ADMIN_PUBLIC_HOST,
    ADMIN_READ_ONLY,
    AUTH_RATE_LIMIT_MAX_REQUESTS,
    AUTH_RATE_LIMIT_WINDOW_SECONDS,
    CORS_ALLOWED_ORIGINS,
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
    AdminProductionReadinessRead,
    AdminReadinessCheck,
    AdminWorkerHeartbeatRead,
    IntegrationQueueHealthRead,
    IntegrationRetryPayload,
    IntegrationRunRead,
    IntegrationRunRetryPayload,
    IntegrationStatusRead,
)
from src.app.services.admin import (
    AdminContext,
    add_admin_audit,
    default_max_attempts,
    enqueue_integration_run,
    require_permission,
)
from src.app.services.admin.jobs import PROCESSING_QUEUE_NAME, SCHEDULED_QUEUE_NAME
from src.app.services.admin.jobs import get_worker_heartbeats
from src.app.services.admin.permissions import ALL_PERMISSIONS
from src.app.services.cache import get_cache_service
from src.database import get_db
from src.database.models import Admin, AdminAlert, AdminRole, IntegrationRun

admin_integrations_router = APIRouter(prefix="/integrations", tags=["admin_integrations"])

PROVIDERS = (
    ("amocrm", "amoCRM", lambda: bool(AMOCRM_ACCESS_TOKEN)),
    ("moysklad", "МойСклад", lambda: bool(MOY_SKLAD_TOKEN)),
    ("intellectmoney", "IntellectMoney", lambda: bool(INTELLECTMONEY_BEARER_TOKEN and INTELLECTMONEY_SHOP_ID)),
    ("cdek", "CDEK", lambda: bool(CDEK_ACCOUNT and CDEK_SECURE_PASSWORD)),
    ("yandex_delivery", "Яндекс Доставка", lambda: bool(YANDEX_DELIVERY_TOKEN)),
    ("telegram", "Telegram", lambda: bool(TELEGRAM_BOT_TOKEN)),
)

REQUIRED_ADMIN_ROUTES = {
    "/api/v1/admin/dashboard",
    "/api/v1/admin/search",
    "/api/v1/admin/orders",
    "/api/v1/admin/customers",
    "/api/v1/admin/tasks",
    "/api/v1/admin/segments",
    "/api/v1/admin/segments/preview",
    "/api/v1/admin/campaigns",
    "/api/v1/admin/campaigns/preview",
    "/api/v1/admin/automations",
    "/api/v1/admin/products",
    "/api/v1/admin/categories",
    "/api/v1/admin/reviews",
    "/api/v1/admin/banners",
    "/api/v1/admin/referrals/summary",
    "/api/v1/admin/analytics",
    "/api/v1/admin/analytics/{section}.csv",
    "/api/v1/admin/integrations/production-readiness",
    "/api/v1/admin/exports",
    "/api/v1/admin/staff",
    "/api/v1/admin/audit",
}

REQUIRED_ADMIN_PERMISSIONS = {
    "dashboard.read",
    "orders.read",
    "orders.transition",
    "orders.recover",
    "customers.read",
    "tasks.read",
    "tasks.manage",
    "segments.read",
    "segments.manage",
    "campaigns.read",
    "campaigns.manage",
    "campaigns.send",
    "automation.read",
    "automation.manage",
    "catalog.read",
    "reviews.read",
    "reviews.moderate",
    "banners.manage",
    "referrals.read",
    "analytics.read",
    "integrations.read",
    "integrations.retry",
    "staff.manage",
    "audit.read",
    "exports.read",
}


async def _idempotent_run(
    db: AsyncSession,
    *,
    idempotency_key: str,
    provider: str,
    operation: str,
    target_type: str | None,
    target_id: str | None,
) -> IntegrationRun | None:
    existing = (await db.execute(
        select(IntegrationRun).where(IntegrationRun.idempotency_key == idempotency_key)
    )).scalar_one_or_none()
    if existing is None:
        return None
    if (
        existing.provider != provider
        or existing.operation != operation
        or existing.target_type != target_type
        or existing.target_id != target_id
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key belongs to another operation")
    return existing


async def _enqueue_or_fail(db: AsyncSession, run: IntegrationRun) -> None:
    try:
        await enqueue_integration_run(run.id)
    except Exception as error:
        run.status = "error"
        run.error = f"Failed to enqueue admin job: {error}"[:8000]
        run.finished_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin job queue is unavailable") from error


@admin_integrations_router.get("", response_model=list[IntegrationStatusRead])
async def list_integrations(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("integrations.read")),
) -> list[IntegrationStatusRead]:
    result: list[IntegrationStatusRead] = []
    for provider, label, configured_fn in PROVIDERS:
        configured = configured_fn()
        latest = (await db.execute(
            select(IntegrationRun)
            .where(IntegrationRun.provider == provider)
            .order_by(IntegrationRun.started_at.desc(), IntegrationRun.id.desc())
            .limit(1)
        )).scalar_one_or_none()
        if not configured:
            state = "disabled"
        elif latest is not None and latest.status == "error":
            state = "error"
        elif latest is not None and latest.status in {"queued", "running", "retrying"}:
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
    target_type: str | None = Query(default=None, max_length=60),
    target_id: str | None = Query(default=None, max_length=160),
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
    if target_type:
        filters.append(IntegrationRun.target_type == target_type)
    if target_id:
        filters.append(IntegrationRun.target_id == target_id)
    total = int((await db.execute(select(func.count(IntegrationRun.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(
        select(IntegrationRun)
        .where(*filters)
        .order_by(IntegrationRun.started_at.desc(), IntegrationRun.id.desc())
        .offset(offset)
        .limit(limit)
    )).scalars().all())
    return AdminPage(items=[IntegrationRunRead.model_validate(row) for row in rows], total=total, limit=limit, offset=offset)


@admin_integrations_router.get("/queue-health", response_model=IntegrationQueueHealthRead)
async def integration_queue_health(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("integrations.read")),
) -> IntegrationQueueHealthRead:
    now = datetime.now(timezone.utc)

    async def count_status(run_status: str) -> int:
        return int((await db.execute(
            select(func.count(IntegrationRun.id)).where(IntegrationRun.status == run_status)
        )).scalar_one())

    queued = await count_status("queued")
    running = await count_status("running")
    retrying = await count_status("retrying")
    failed_24h = int((await db.execute(select(func.count(IntegrationRun.id)).where(
        IntegrationRun.status == "error",
        IntegrationRun.finished_at >= now - timedelta(hours=24),
    ))).scalar_one())
    stale_before = now - timedelta(seconds=ADMIN_JOB_STALE_SECONDS)
    stale_running = int((await db.execute(select(func.count(IntegrationRun.id)).where(
        IntegrationRun.status == "running",
        or_(IntegrationRun.heartbeat_at < stale_before, IntegrationRun.heartbeat_at.is_(None)),
    ))).scalar_one())
    oldest_pending_at = (await db.execute(select(func.min(IntegrationRun.started_at)).where(
        IntegrationRun.status.in_(("queued", "retrying")),
    ))).scalar_one()

    queue_available = False
    queue_depth = processing_depth = scheduled_depth = 0
    cache = get_cache_service()
    if cache.client is None:
        await cache.connect()
    if cache.client is not None:
        try:
            queue_depth = int(await cache.client.llen(PROCESSING_QUEUE_NAME.removesuffix(":processing")))
            processing_depth = int(await cache.client.llen(PROCESSING_QUEUE_NAME))
            scheduled_depth = int(await cache.client.zcard(SCHEDULED_QUEUE_NAME))
            queue_available = True
        except Exception:
            queue_available = False

    return IntegrationQueueHealthRead(
        queue_available=queue_available,
        queue_depth=queue_depth,
        processing_depth=processing_depth,
        scheduled_depth=scheduled_depth,
        queued=queued,
        running=running,
        retrying=retrying,
        failed_24h=failed_24h,
        stale_running=stale_running,
        oldest_pending_at=oldest_pending_at,
    )


def _readiness_status(checks: list[AdminReadinessCheck]) -> str:
    statuses = {check.status for check in checks}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    if "unknown" in statuses:
        return "unknown"
    return "ok"


def _backup_check(now: datetime) -> AdminReadinessCheck:
    if not ADMIN_BACKUP_STATUS_PATH:
        return AdminReadinessCheck(
            key="backups",
            label_ru="Бэкапы",
            label_en="Backups",
            status="unknown",
            message_ru="Не указан ADMIN_BACKUP_STATUS_PATH; свежесть бэкапа нужно подтвердить на сервере.",
            message_en="ADMIN_BACKUP_STATUS_PATH is not set; backup freshness must be confirmed on the server.",
        )
    path = Path(ADMIN_BACKUP_STATUS_PATH)
    if not path.exists():
        return AdminReadinessCheck(
            key="backups",
            label_ru="Бэкапы",
            label_en="Backups",
            status="error",
            message_ru="Файл статуса бэкапа не найден.",
            message_en="Backup status file was not found.",
            details={"path": str(path)},
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        last_success = datetime.fromisoformat(str(payload.get("last_success_at")))
        if last_success.tzinfo is None:
            last_success = last_success.replace(tzinfo=timezone.utc)
    except Exception:
        return AdminReadinessCheck(
            key="backups",
            label_ru="Бэкапы",
            label_en="Backups",
            status="error",
            message_ru="Файл статуса бэкапа не читается как JSON с last_success_at.",
            message_en="Backup status file is not readable as JSON with last_success_at.",
            details={"path": str(path)},
        )
    age_hours = (now - last_success.astimezone(timezone.utc)).total_seconds() / 3600
    status_value = "ok" if age_hours <= 26 else "warning"
    return AdminReadinessCheck(
        key="backups",
        label_ru="Бэкапы",
        label_en="Backups",
        status=status_value,
        message_ru="Последний успешный бэкап свежий." if status_value == "ok" else "Последний успешный бэкап старше 26 часов.",
        message_en="Last successful backup is fresh." if status_value == "ok" else "Last successful backup is older than 26 hours.",
        details={"path": str(path), "last_success_at": last_success.isoformat(), "age_hours": round(age_hours, 1)},
    )


@admin_integrations_router.get("/production-readiness", response_model=AdminProductionReadinessRead)
async def production_readiness(
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("integrations.read")),
) -> AdminProductionReadinessRead:
    now = datetime.now(timezone.utc)
    checks: list[AdminReadinessCheck] = []
    workers: list[AdminWorkerHeartbeatRead] = []

    await db.execute(select(func.count(IntegrationRun.id)))
    checks.append(AdminReadinessCheck(
        key="api_database",
        label_ru="API и база",
        label_en="API and database",
        status="ok",
        message_ru="Admin API отвечает и база доступна.",
        message_en="Admin API responds and the database is reachable.",
    ))

    route_paths = {getattr(route, "path", "") for route in request.app.routes}
    missing_routes = sorted(REQUIRED_ADMIN_ROUTES - route_paths)
    checks.append(AdminReadinessCheck(
        key="admin_route_coverage",
        label_ru="Покрытие разделов",
        label_en="Section coverage",
        status="error" if missing_routes else "ok",
        message_ru="Все ключевые admin-разделы подключены." if not missing_routes else "Часть ключевых admin-разделов не подключена.",
        message_en="All key admin sections are mounted." if not missing_routes else "Some key admin sections are not mounted.",
        details={"missing_routes": missing_routes, "checked_routes": sorted(REQUIRED_ADMIN_ROUTES)},
    ))

    missing_permissions = sorted(REQUIRED_ADMIN_PERMISSIONS - set(ALL_PERMISSIONS))
    superadmin_roles = int((await db.execute(select(func.count(AdminRole.id)).where(AdminRole.code == "Superadmin"))).scalar_one())
    active_admins = int((await db.execute(select(func.count(Admin.user_id)).where(Admin.is_active.is_(True)))).scalar_one())
    active_without_mfa = int((await db.execute(select(func.count(Admin.user_id)).where(
        Admin.is_active.is_(True),
        Admin.mfa_confirmed_at.is_(None),
    ))).scalar_one())
    checks.append(AdminReadinessCheck(
        key="rbac_mfa",
        label_ru="RBAC и MFA",
        label_en="RBAC and MFA",
        status="error" if missing_permissions or active_without_mfa else "warning" if not superadmin_roles or not active_admins else "ok",
        message_ru=(
            "Права, роли и MFA готовы."
            if not missing_permissions and not active_without_mfa and superadmin_roles and active_admins
            else "Нужно проверить роли, права или MFA активных администраторов."
        ),
        message_en=(
            "Permissions, roles and MFA are ready."
            if not missing_permissions and not active_without_mfa and superadmin_roles and active_admins
            else "Roles, permissions or active admin MFA need attention."
        ),
        details={
            "missing_permissions": missing_permissions,
            "superadmin_roles": superadmin_roles,
            "active_admins": active_admins,
            "active_without_mfa": active_without_mfa,
        },
    ))

    cors_wildcard = "*" in CORS_ALLOWED_ORIGINS
    checks.append(AdminReadinessCheck(
        key="security_config",
        label_ru="Безопасность входа",
        label_en="Login security",
        status="error" if cors_wildcard else "warning" if not ADMIN_COOKIE_SECURE else "ok",
        message_ru=(
            "Cookie, CORS и rate limit настроены для production."
            if ADMIN_COOKIE_SECURE and not cors_wildcard
            else "Проверьте Secure cookie и production CORS."
        ),
        message_en=(
            "Cookie, CORS and rate limiting are production-ready."
            if ADMIN_COOKIE_SECURE and not cors_wildcard
            else "Check Secure cookie and production CORS."
        ),
        details={
            "admin_cookie_secure": ADMIN_COOKIE_SECURE,
            "cors_allowed_origins": CORS_ALLOWED_ORIGINS,
            "auth_rate_limit_max_requests": AUTH_RATE_LIMIT_MAX_REQUESTS,
            "auth_rate_limit_window_seconds": AUTH_RATE_LIMIT_WINDOW_SECONDS,
        },
    ))

    queue = await integration_queue_health(db=db, _=context)
    if not queue.queue_available:
        queue_status = "error"
    elif queue.stale_running:
        queue_status = "warning"
    else:
        queue_status = "ok"
    checks.append(AdminReadinessCheck(
        key="queues",
        label_ru="Очереди",
        label_en="Queues",
        status=queue_status,
        message_ru="Redis-очередь доступна." if queue.queue_available else "Redis-очередь недоступна.",
        message_en="Redis queue is available." if queue.queue_available else "Redis queue is unavailable.",
        details=queue.model_dump(mode="json"),
    ))

    heartbeat_names = ["admin_jobs", "admin_automation"]
    try:
        heartbeat_values = await get_worker_heartbeats(heartbeat_names)
    except Exception:
        heartbeat_values = {name: None for name in heartbeat_names}
    for worker_name in heartbeat_names:
        last_seen = heartbeat_values.get(worker_name)
        stale_after = max(ADMIN_JOB_STALE_SECONDS * 2, 120)
        if last_seen is None:
            worker_status = "unknown"
        else:
            worker_status = "ok" if (now - last_seen.astimezone(timezone.utc)).total_seconds() <= stale_after else "warning"
        workers.append(AdminWorkerHeartbeatRead(
            name=worker_name,
            status=worker_status,
            last_seen_at=last_seen,
            stale_after_seconds=stale_after,
        ))
    worker_statuses = {worker.status for worker in workers}
    checks.append(AdminReadinessCheck(
        key="workers",
        label_ru="Фоновые процессы",
        label_en="Workers",
        status="warning" if "warning" in worker_statuses else "unknown" if "unknown" in worker_statuses else "ok",
        message_ru="Пульс worker’ов получен." if worker_statuses == {"ok"} else "Не все worker’ы недавно отметились.",
        message_en="Worker heartbeats are fresh." if worker_statuses == {"ok"} else "Not all workers have a recent heartbeat.",
    ))

    integrations = await list_integrations(db=db, _=context)
    integration_errors = [item.provider for item in integrations if item.status == "error"]
    unconfigured = [item.provider for item in integrations if not item.configured]
    checks.append(AdminReadinessCheck(
        key="integrations",
        label_ru="Интеграции",
        label_en="Integrations",
        status="error" if integration_errors else "warning" if unconfigured else "ok",
        message_ru="Есть интеграции с ошибками." if integration_errors else "Часть интеграций не настроена." if unconfigured else "Ключевые интеграции настроены.",
        message_en="Some integrations have errors." if integration_errors else "Some integrations are not configured." if unconfigured else "Key integrations are configured.",
        details={"errors": integration_errors, "unconfigured": unconfigured},
    ))

    active_alerts = int((await db.execute(select(func.count(AdminAlert.id)).where(AdminAlert.resolved_at.is_(None)))).scalar_one())
    checks.append(AdminReadinessCheck(
        key="active_alerts",
        label_ru="Активные сбои",
        label_en="Active alerts",
        status="warning" if active_alerts else "ok",
        message_ru=f"Активных сбоев: {active_alerts}.",
        message_en=f"Active alerts: {active_alerts}.",
        details={"active_alerts": active_alerts},
    ))

    checks.append(_backup_check(now))
    checks.append(AdminReadinessCheck(
        key="domain_ssl",
        label_ru="Домен и SSL",
        label_en="Domain and SSL",
        status="ok" if ADMIN_PUBLIC_HOST else "unknown",
        message_ru=f"Публичный host задан: {ADMIN_PUBLIC_HOST}." if ADMIN_PUBLIC_HOST else "Публичный host не задан.",
        message_en=f"Public host is configured: {ADMIN_PUBLIC_HOST}." if ADMIN_PUBLIC_HOST else "Public host is not configured.",
        details={"host": ADMIN_PUBLIC_HOST},
    ))
    checks.append(AdminReadinessCheck(
        key="mutation_mode",
        label_ru="Режим изменений",
        label_en="Mutation mode",
        status="warning" if ADMIN_READ_ONLY else "ok",
        message_ru="Read-only режим включён." if ADMIN_READ_ONLY else "Изменения в админке разрешены.",
        message_en="Read-only mode is enabled." if ADMIN_READ_ONLY else "Admin mutations are enabled.",
    ))

    checklist_summary = {
        "ok": sum(1 for check in checks if check.status == "ok"),
        "warning": sum(1 for check in checks if check.status == "warning"),
        "error": sum(1 for check in checks if check.status == "error"),
        "unknown": sum(1 for check in checks if check.status == "unknown"),
    }

    return AdminProductionReadinessRead(
        overall_status=_readiness_status(checks),
        generated_at=now,
        public_host=ADMIN_PUBLIC_HOST,
        checklist_summary=checklist_summary,
        checks=checks,
        workers=workers,
    )


@admin_integrations_router.post("/runs/{run_id}/retry", response_model=IntegrationRunRead, status_code=status.HTTP_202_ACCEPTED)
async def retry_integration_run(
    run_id: int,
    payload: IntegrationRunRetryPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("integrations.retry", write=True)),
) -> IntegrationRunRead:
    source = await db.get(IntegrationRun, run_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration run not found")
    if source.status != "error":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed operations can be retried")
    existing = await _idempotent_run(
        db,
        idempotency_key=payload.idempotency_key,
        provider=source.provider,
        operation=source.operation,
        target_type=source.target_type,
        target_id=source.target_id,
    )
    if existing is not None:
        return IntegrationRunRead.model_validate(existing)

    run = IntegrationRun(
        provider=source.provider,
        operation=source.operation,
        status="queued",
        requested_by_user_id=context.user.id,
        target_type=source.target_type,
        target_id=source.target_id,
        retry_of_id=source.id,
        attempts=0,
        max_attempts=default_max_attempts(),
        input_json=source.input_json,
        idempotency_key=payload.idempotency_key,
    )
    db.add(run)
    await db.flush()
    await add_admin_audit(
        db,
        request,
        context,
        action="integration.run.retry",
        entity_type="integration_run",
        entity_id=run.id,
        after={"provider": run.provider, "operation": run.operation, "retry_of_id": source.id},
    )
    await db.commit()
    await db.refresh(run)
    await _enqueue_or_fail(db, run)
    return IntegrationRunRead.model_validate(run)


@admin_integrations_router.post("/{provider}/retry", response_model=IntegrationRunRead, status_code=status.HTTP_202_ACCEPTED)
async def retry_integration(
    provider: str,
    payload: IntegrationRetryPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("integrations.retry", write=True)),
) -> IntegrationRunRead:
    existing = await _idempotent_run(
        db,
        idempotency_key=payload.idempotency_key,
        provider=provider,
        operation=payload.operation,
        target_type=None,
        target_id=None,
    )
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
        action="integration.retry",
        entity_type="integration_run",
        entity_id=run.id,
        after={"provider": provider, "operation": payload.operation},
    )
    await db.commit()
    await db.refresh(run)
    await _enqueue_or_fail(db, run)
    return IntegrationRunRead.model_validate(run)
