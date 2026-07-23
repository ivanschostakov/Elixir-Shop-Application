from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.admin.schemas import AdminExportCreatePayload, AdminExportRead
from src.app.services.admin import AdminContext, add_admin_audit, default_max_attempts, enqueue_integration_run, require_permission
from src.app.services.admin.exports import RESOURCE_PERMISSIONS, normalize_export_payload, resolve_export_file
from src.database import get_db
from src.database.models import IntegrationRun

admin_exports_router = APIRouter(prefix="/exports", tags=["admin_exports"])


def _assert_resource_permission(context: AdminContext, resource: str) -> None:
    permission = RESOURCE_PERMISSIONS.get(resource)
    if permission is None or not context.has_permission(permission):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission for export: {resource}")


def _assert_export_owner(context: AdminContext, run: IntegrationRun) -> None:
    if run.requested_by_user_id != context.user.id and "*" not in context.permissions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")


def _export_read(run: IntegrationRun) -> AdminExportRead:
    source = run.counters_json or run.input_json or {}
    return AdminExportRead(
        id=run.id,
        resource=str(source.get("resource") or run.target_id or ""),
        format=str(source.get("format") or run.input_json.get("format") or ""),
        status=run.status,
        rows=source.get("rows") if isinstance(source.get("rows"), int) else None,
        file_name=source.get("file_name") if isinstance(source.get("file_name"), str) else None,
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


async def _get_export(db: AsyncSession, run_id: int) -> IntegrationRun:
    run = await db.get(IntegrationRun, run_id)
    if run is None or run.provider != "admin" or run.operation != "export":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    return run


@admin_exports_router.post("", response_model=AdminExportRead, status_code=status.HTTP_202_ACCEPTED)
async def create_export(
    payload: AdminExportCreatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("exports.read", write=True)),
) -> AdminExportRead:
    _assert_resource_permission(context, payload.resource)
    try:
        normalized = normalize_export_payload(payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    existing = (await db.execute(
        select(IntegrationRun).where(IntegrationRun.idempotency_key == payload.idempotency_key)
    )).scalar_one_or_none()
    if existing is not None:
        if existing.provider != "admin" or existing.operation != "export" or existing.input_json != normalized:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key belongs to another operation")
        return _export_read(existing)

    run = IntegrationRun(
        provider="admin",
        operation="export",
        status="queued",
        requested_by_user_id=context.user.id,
        target_type="export",
        target_id=payload.resource,
        attempts=0,
        max_attempts=default_max_attempts(),
        input_json=normalized,
        idempotency_key=payload.idempotency_key,
    )
    db.add(run)
    await db.flush()
    await add_admin_audit(
        db,
        request,
        context,
        action="export.queued",
        entity_type="export",
        entity_id=run.id,
        after={
            "resource": payload.resource,
            "format": payload.format,
            "columns": normalized["columns"],
            "selected_count": len(normalized["selected_ids"]),
        },
    )
    await db.commit()
    await db.refresh(run)
    try:
        await enqueue_integration_run(run.id)
    except Exception as error:
        run.status = "error"
        run.error = f"Failed to enqueue admin export: {error}"[:8000]
        run.finished_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin export queue is unavailable") from error
    return _export_read(run)


@admin_exports_router.get("/{run_id}", response_model=AdminExportRead)
async def get_export(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("exports.read")),
) -> AdminExportRead:
    run = await _get_export(db, run_id)
    _assert_export_owner(context, run)
    _assert_resource_permission(context, run.target_id or "")
    return _export_read(run)


@admin_exports_router.get("/{run_id}/download")
async def download_export(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("exports.read")),
) -> FileResponse:
    run = await _get_export(db, run_id)
    _assert_export_owner(context, run)
    _assert_resource_permission(context, run.target_id or "")
    if run.status != "success":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export is not ready")
    file_name = (run.counters_json or {}).get("file_name")
    path = resolve_export_file(file_name) if isinstance(file_name, str) else None
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file not found")
    media_type = "text/csv; charset=utf-8" if path.suffix == ".csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(path, media_type=media_type, filename=path.name)
