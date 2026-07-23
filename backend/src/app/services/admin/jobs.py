import json
import logging

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_, select

from config import (
    ADMIN_JOB_MAX_ATTEMPTS,
    ADMIN_JOB_QUEUE_NAME,
    ADMIN_JOB_STALE_SECONDS,
)
from src.app.services.cache import get_cache_service
from src.app.services.admin.exports import generate_admin_export
from src.app.services.admin.campaigns import execute_push_campaign, mark_push_campaign_failed
from src.app.services.admin.alerts import raise_admin_alert, resolve_admin_alert
from src.app.services.admin.order_transitions import transition_is_allowed, transition_status_id
from src.app.services.orders import apply_amocrm_status_update, create_delivery_for_order, recheck_payment_status_for_admin
from src.database import SessionLocal
from src.database.crud import get_order_by_id, update_order
from src.database.models import AdminAuditLog, IntegrationRun
from src.database.schemas import OrderUpdate
from src.database.models.orders.history import ORDER_STATUS_CODE_VALUES, get_order_status_code
from src.integrations.amocrm import get_amocrm_client
from src.integrations.moysklad import sync_moysklad_product_catalog
from src.integrations.moysklad.order_sync import sync_order_to_moysklad

log = logging.getLogger(__name__)
amocrm_client = get_amocrm_client()

PROCESSING_QUEUE_NAME = f"{ADMIN_JOB_QUEUE_NAME}:processing"
SCHEDULED_QUEUE_NAME = f"{ADMIN_JOB_QUEUE_NAME}:scheduled"
QUEUE_MARKER_PREFIX = f"{ADMIN_JOB_QUEUE_NAME}:run"
WORKER_HEARTBEAT_PREFIX = f"{ADMIN_JOB_QUEUE_NAME}:heartbeat"
PENDING_RUN_STATUSES = frozenset(("queued", "retrying"))


def _order_audit_snapshot(order) -> dict[str, Any]:
    return {
        "id": order.id,
        "order_code": order.order_code,
        "status": order.status,
        "status_code": get_order_status_code(order),
        "payment_status": order.payment_status,
        "is_active": order.is_active,
        "is_paid": order.is_paid,
        "is_canceled": order.is_canceled,
        "is_shipped": order.is_shipped,
        "amocrm_lead_id": order.amocrm_lead_id,
        "delivery_created_at": order.delivery_created_at,
        "delivery_provider_ref": order.delivery_provider_ref,
        "moysklad_customerorder_id": str(order.moysklad_customerorder_id) if order.moysklad_customerorder_id else None,
        "moysklad_invoiceout_id": str(order.moysklad_invoiceout_id) if order.moysklad_invoiceout_id else None,
        "updated_at": order.updated_at,
    }


def retry_delay_seconds(attempts: int) -> int:
    return min(5 * (2 ** max(0, attempts - 1)), 300)


def is_retryable_error(error: Exception) -> bool:
    if not isinstance(error, HTTPException):
        return True
    return error.status_code == 429 or error.status_code >= 500


def encode_job(run_id: int) -> str:
    return json.dumps({"run_id": int(run_id)}, separators=(",", ":"))


def parse_job(raw_payload: str) -> int | None:
    try:
        payload = json.loads(raw_payload)
        run_id = int(payload["run_id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return run_id if run_id > 0 else None


async def _redis_client():
    cache = get_cache_service()
    if cache.client is None:
        await cache.connect()
    if cache.client is None:
        raise RuntimeError("Redis admin job queue is unavailable")
    return cache.client


async def enqueue_integration_run(run_id: int, *, delay_seconds: int = 0) -> None:
    redis = await _redis_client()
    if delay_seconds > 0:
        await redis.zadd(SCHEDULED_QUEUE_NAME, {str(run_id): datetime.now(timezone.utc).timestamp() + delay_seconds})
        return

    marker_key = f"{QUEUE_MARKER_PREFIX}:{run_id}:queued"
    marker_created = await redis.set(marker_key, "1", ex=max(ADMIN_JOB_STALE_SECONDS * 2, 600), nx=True)
    if marker_created:
        await redis.lpush(ADMIN_JOB_QUEUE_NAME, encode_job(run_id))


async def acknowledge_queued_marker(run_id: int) -> None:
    redis = await _redis_client()
    await redis.delete(f"{QUEUE_MARKER_PREFIX}:{run_id}:queued")


async def record_worker_heartbeat(worker_name: str) -> None:
    redis = await _redis_client()
    await redis.set(f"{WORKER_HEARTBEAT_PREFIX}:{worker_name}", datetime.now(timezone.utc).isoformat(), ex=max(ADMIN_JOB_STALE_SECONDS * 3, 900))


async def get_worker_heartbeats(worker_names: list[str]) -> dict[str, datetime | None]:
    redis = await _redis_client()
    result: dict[str, datetime | None] = {}
    for worker_name in worker_names:
        raw_value = await redis.get(f"{WORKER_HEARTBEAT_PREFIX}:{worker_name}")
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode()
        try:
            result[worker_name] = datetime.fromisoformat(raw_value) if raw_value else None
        except (TypeError, ValueError):
            result[worker_name] = None
    return result


async def move_due_scheduled_runs() -> int:
    redis = await _redis_client()
    due = await redis.zrangebyscore(SCHEDULED_QUEUE_NAME, min="-inf", max=datetime.now(timezone.utc).timestamp(), start=0, num=200)
    moved = 0
    for raw_run_id in due:
        if not await redis.zrem(SCHEDULED_QUEUE_NAME, raw_run_id):
            continue
        try:
            run_id = int(raw_run_id)
        except (TypeError, ValueError):
            continue
        await enqueue_integration_run(run_id)
        moved += 1
    return moved


async def recover_processing_queue() -> int:
    redis = await _redis_client()
    payloads = await redis.lrange(PROCESSING_QUEUE_NAME, 0, -1)
    run_ids: list[int] = []
    for payload in payloads:
        run_id = parse_job(payload)
        await redis.lrem(PROCESSING_QUEUE_NAME, 1, payload)
        if run_id is not None:
            run_ids.append(run_id)

    if not run_ids:
        return 0

    now = datetime.now(timezone.utc)
    to_enqueue: list[int] = []
    async with SessionLocal() as db:
        rows = list((await db.execute(
            select(IntegrationRun).where(IntegrationRun.id.in_(run_ids)).with_for_update(skip_locked=True)
        )).scalars().all())
        for row in rows:
            if row.status == "running":
                if row.attempts >= row.max_attempts:
                    row.status = "error"
                    row.finished_at = now
                    row.error = ((row.error or "") + "\nWorker stopped before acknowledgement").strip()[:8000]
                    continue
                row.status = "retrying"
                row.next_attempt_at = now
                row.error = ((row.error or "") + "\nRecovered after worker restart").strip()[:8000]
            if row.status in PENDING_RUN_STATUSES:
                to_enqueue.append(row.id)
        await db.commit()

    for run_id in to_enqueue:
        await redis.delete(f"{QUEUE_MARKER_PREFIX}:{run_id}:queued")
        await enqueue_integration_run(run_id)
    return len(to_enqueue)


async def recover_due_database_runs() -> int:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=ADMIN_JOB_STALE_SECONDS)
    due_ids: list[int] = []
    async with SessionLocal() as db:
        stale_rows = list((await db.execute(
            select(IntegrationRun).where(
                IntegrationRun.status == "running",
                or_(
                    IntegrationRun.heartbeat_at < stale_before,
                    and_(IntegrationRun.heartbeat_at.is_(None), IntegrationRun.started_at < stale_before),
                ),
            ).with_for_update(skip_locked=True).limit(200)
        )).scalars().all())
        for row in stale_rows:
            if row.attempts >= row.max_attempts:
                row.status = "error"
                row.finished_at = now
                row.error = ((row.error or "") + "\nWorker stopped before completion").strip()[:8000]
            else:
                row.status = "retrying"
                row.next_attempt_at = now
                row.error = ((row.error or "") + "\nRecovered after worker interruption").strip()[:8000]

        due_ids = list((await db.execute(
            select(IntegrationRun.id).where(
                IntegrationRun.status.in_(PENDING_RUN_STATUSES),
                or_(IntegrationRun.next_attempt_at.is_(None), IntegrationRun.next_attempt_at <= now),
            ).order_by(IntegrationRun.started_at.asc()).limit(200)
        )).scalars().all())
        await db.commit()

    for run_id in due_ids:
        await enqueue_integration_run(int(run_id))
    return len(due_ids)


async def _run_order_operation(operation: str, target_id: str | None) -> dict[str, Any]:
    try:
        order_id = int(target_id or "")
    except ValueError as error:
        raise RuntimeError("Integration run has an invalid order target") from error

    async with SessionLocal() as db:
        order = await get_order_by_id(db, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")

        if operation == "payment_check":
            return await recheck_payment_status_for_admin(db, order=order)

        if operation == "moysklad_order_sync":
            result = await sync_order_to_moysklad(db, order=order, user=order.user)
            if result.skipped_reason:
                raise RuntimeError(f"MoySklad order sync skipped: {result.skipped_reason}")
            return jsonable_encoder(result.as_dict())

        if operation == "delivery_create":
            if order.delivery_created_at is not None or order.delivery_provider_ref:
                return {
                    "order_id": order.id,
                    "already_created": True,
                    "delivery_provider_ref": order.delivery_provider_ref,
                }
            patch = await create_delivery_for_order(order)
            if not patch:
                raise RuntimeError("Delivery provider did not return a delivery reference")
            patch["delivery_created_at"] = datetime.now(timezone.utc)
            updated = await update_order(db, order, OrderUpdate(**patch), commit=True)
            return {
                "order_id": updated.id,
                "delivery_provider_ref": updated.delivery_provider_ref,
                "yandex_request_id": updated.yandex_request_id,
            }

        if operation == "status_transition":
            return await _run_order_status_transition(db, order=order)

    raise RuntimeError(f"Unsupported order operation: {operation}")


async def _audit_worker_order_transition(
    db: Any,
    *,
    run: IntegrationRun,
    order_id: int,
    before: dict[str, Any],
    after: dict[str, Any],
    from_status_code: str,
    to_status_code: str,
    reason: str | None,
) -> None:
    db.add(AdminAuditLog(
        actor_user_id=run.requested_by_user_id,
        action="order.transition.applied",
        entity_type="order",
        entity_id=str(order_id),
        before_json=jsonable_encoder(before),
        after_json=jsonable_encoder(after),
        context_json=jsonable_encoder({
            "run_id": run.id,
            "provider": run.provider,
            "operation": run.operation,
            "from_status_code": from_status_code,
            "to_status_code": to_status_code,
            "reason": reason,
            "source": "admin_job_worker",
        }),
    ))
    await db.flush()


async def _run_order_status_transition(db: Any, *, order) -> dict[str, Any]:
    run = (await db.execute(
        select(IntegrationRun)
        .where(
            IntegrationRun.target_type == "order",
            IntegrationRun.target_id == str(order.id),
            IntegrationRun.operation == "status_transition",
            IntegrationRun.status == "running",
        )
        .order_by(IntegrationRun.started_at.desc(), IntegrationRun.id.desc())
        .limit(1)
    )).scalar_one_or_none()
    if run is None:
        raise RuntimeError("Status transition run context was not found")

    input_json = run.input_json or {}
    target_code = input_json.get("to_status_code")
    if target_code not in ORDER_STATUS_CODE_VALUES:
        raise HTTPException(status_code=422, detail="Integration run has an invalid target status")
    reason = (input_json.get("reason") or "").strip() or None
    current_code = get_order_status_code(order)
    if current_code == target_code:
        return {
            "order_id": order.id,
            "already_applied": True,
            "status_code": current_code,
        }
    if not transition_is_allowed(current_code, target_code):
        raise HTTPException(
            status_code=409,
            detail={"code": "invalid_transition_after_queue", "from": current_code, "to": target_code},
        )
    if target_code == "canceled" and not reason:
        raise HTTPException(status_code=422, detail="Cancellation reason is required")
    if not order.amocrm_lead_id:
        raise HTTPException(status_code=409, detail="Order is not linked to amoCRM")

    before = jsonable_encoder(_order_audit_snapshot(order))
    target_status_id = transition_status_id(target_code)
    await amocrm_client.update_lead_status(int(order.amocrm_lead_id), target_status_id)
    updated_order = await apply_amocrm_status_update(db, order=order, status_id=target_status_id)
    updated_order = await get_order_by_id(db, updated_order.id)
    if updated_order is None:
        raise HTTPException(status_code=500, detail="Failed to reload order after status transition")
    after = jsonable_encoder(_order_audit_snapshot(updated_order))
    await _audit_worker_order_transition(
        db,
        run=run,
        order_id=updated_order.id,
        before=before,
        after=after,
        from_status_code=current_code,
        to_status_code=target_code,
        reason=reason,
    )
    await db.commit()
    return {
        "order_id": updated_order.id,
        "previous_status_code": current_code,
        "status_code": target_code,
        "amocrm_lead_id": updated_order.amocrm_lead_id,
        "reason": reason,
    }


async def _execute_operation(run_id: int) -> dict[str, Any]:
    async with SessionLocal() as db:
        run = await db.get(IntegrationRun, run_id)
        if run is None:
            raise RuntimeError("Integration run not found")
        provider = run.provider
        operation = run.operation
        target_type = run.target_type
        target_id = run.target_id
        input_json = run.input_json

    if provider == "moysklad" and operation == "catalog_sync" and target_type is None:
        stats = await sync_moysklad_product_catalog()
        return jsonable_encoder(stats.as_dict())
    if provider == "admin" and operation == "export" and target_type == "export":
        return await generate_admin_export(input_json, run_id)
    if provider == "admin" and operation == "push_campaign" and target_type == "campaign":
        try:
            campaign_id = int(target_id or "")
        except ValueError as error:
            raise RuntimeError("Integration run has an invalid campaign target") from error
        return await execute_push_campaign(campaign_id)
    if provider == "admin" and operation == "order_automation" and target_type == "automation_rule":
        try:
            rule_id = int(target_id or "")
        except ValueError as error:
            raise RuntimeError("Integration run has an invalid automation rule target") from error
        from src.app.services.admin.automation import execute_order_automation_rule

        return await execute_order_automation_rule(rule_id, include_disabled=bool(input_json.get("include_disabled")))
    if target_type == "order":
        return await _run_order_operation(operation, target_id)
    raise RuntimeError(f"Unsupported integration operation: {provider}.{operation}")


def _error_text(error: Exception) -> str:
    if isinstance(error, HTTPException):
        return str(error.detail)[:8000]
    return str(error)[:8000] or error.__class__.__name__


async def execute_integration_run(run_id: int) -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        run = (await db.execute(
            select(IntegrationRun).where(IntegrationRun.id == run_id).with_for_update()
        )).scalar_one_or_none()
        if run is None or run.status not in PENDING_RUN_STATUSES:
            return
        run.status = "running"
        run.attempts += 1
        run.heartbeat_at = now
        run.next_attempt_at = None
        run.finished_at = None
        await db.commit()

    try:
        counters = await _execute_operation(run_id)
    except Exception as error:
        log.exception("Admin integration run failed run_id=%s", run_id)
        retry_delay: int | None = None
        failed_campaign_id: int | None = None
        failure_alert: dict[str, Any] | None = None
        async with SessionLocal() as db:
            run = await db.get(IntegrationRun, run_id)
            if run is None:
                return
            run.error = _error_text(error)
            run.heartbeat_at = datetime.now(timezone.utc)
            if is_retryable_error(error) and run.attempts < run.max_attempts:
                retry_delay = retry_delay_seconds(run.attempts)
                run.status = "retrying"
                run.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
            else:
                run.status = "error"
                run.finished_at = datetime.now(timezone.utc)
                run.next_attempt_at = None
                alert_path = (
                    f"/sales/orders/{run.target_id}" if run.target_type == "order"
                    else "/automation" if run.target_type == "automation_rule"
                    else "/marketing" if run.target_type == "campaign"
                    else "/integrations"
                )
                failure_alert = {
                    "severity": "error",
                    "source": "integration",
                    "code": "integration_run_failed",
                    "title_ru": "Сбой фоновой операции",
                    "title_en": "Background operation failed",
                    "message": f"{run.provider}.{run.operation}: {run.error}",
                    "fingerprint": f"integration:{run.provider}:{run.operation}:{run.target_type or '-'}:{run.target_id or '-'}",
                    "entity_type": run.target_type or "integration_run",
                    "entity_id": run.target_id or run.id,
                    "path": alert_path,
                }
                if run.provider == "admin" and run.operation == "push_campaign" and run.target_type == "campaign":
                    try:
                        failed_campaign_id = int(run.target_id or "")
                    except ValueError:
                        failed_campaign_id = None
            await db.commit()
        if failure_alert is not None:
            try:
                async with SessionLocal() as alert_db:
                    await raise_admin_alert(alert_db, **failure_alert)
                    await alert_db.commit()
            except Exception:
                log.exception("Failed to create integration failure alert run_id=%s", run_id)
        if retry_delay is not None:
            try:
                await enqueue_integration_run(run_id, delay_seconds=retry_delay)
            except Exception:
                log.exception("Failed to schedule admin integration retry run_id=%s", run_id)
        elif failed_campaign_id is not None:
            await mark_push_campaign_failed(failed_campaign_id, _error_text(error))
        return

    success_fingerprint: str | None = None
    async with SessionLocal() as db:
        run = await db.get(IntegrationRun, run_id)
        if run is None:
            return
        run.status = "success"
        run.counters_json = jsonable_encoder(counters)
        run.error = None
        run.heartbeat_at = datetime.now(timezone.utc)
        run.next_attempt_at = None
        run.finished_at = datetime.now(timezone.utc)
        success_fingerprint = f"integration:{run.provider}:{run.operation}:{run.target_type or '-'}:{run.target_id or '-'}"
        await db.commit()
    if success_fingerprint is not None:
        try:
            async with SessionLocal() as alert_db:
                if await resolve_admin_alert(alert_db, fingerprint=success_fingerprint):
                    await alert_db.commit()
        except Exception:
            log.exception("Failed to resolve integration alert run_id=%s", run_id)


def default_max_attempts() -> int:
    return max(1, ADMIN_JOB_MAX_ATTEMPTS)
