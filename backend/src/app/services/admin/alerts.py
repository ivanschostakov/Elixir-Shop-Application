from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.database.models import AdminAlert, AdminAlertReadReceipt


async def raise_admin_alert(
    db: AsyncSession,
    *,
    severity: str,
    source: str,
    code: str,
    title_ru: str,
    title_en: str,
    message: str,
    fingerprint: str,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    path: str | None = None,
    occurred_at: datetime | None = None,
) -> AdminAlert:
    normalized_fingerprint = fingerprint[:160]
    current_time = occurred_at or ufa_now()
    row = (await db.execute(
        select(AdminAlert).where(AdminAlert.fingerprint == normalized_fingerprint).with_for_update()
    )).scalar_one_or_none()
    if row is None:
        row = AdminAlert(
            severity=severity,
            source=source,
            code=code,
            title_ru=title_ru[:240],
            title_en=title_en[:240],
            message=message[:8000],
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            path=path,
            fingerprint=normalized_fingerprint,
            occurrence_count=1,
            last_occurred_at=current_time,
        )
        db.add(row)
        await db.flush()
        return row

    row.severity = severity
    row.source = source
    row.code = code
    row.title_ru = title_ru[:240]
    row.title_en = title_en[:240]
    row.message = message[:8000]
    row.entity_type = entity_type
    row.entity_id = str(entity_id) if entity_id is not None else None
    row.path = path
    row.last_occurred_at = current_time
    row.occurrence_count += 1
    row.resolved_at = None
    row.resolved_by_user_id = None
    await db.execute(delete(AdminAlertReadReceipt).where(AdminAlertReadReceipt.alert_id == row.id))
    await db.flush()
    return row


async def resolve_admin_alert(
    db: AsyncSession,
    *,
    fingerprint: str,
    resolved_by_user_id: int | None = None,
    resolved_at: datetime | None = None,
) -> bool:
    row = (await db.execute(
        select(AdminAlert).where(AdminAlert.fingerprint == fingerprint[:160]).with_for_update()
    )).scalar_one_or_none()
    if row is None or row.resolved_at is not None:
        return False
    row.resolved_at = resolved_at or ufa_now()
    row.resolved_by_user_id = resolved_by_user_id
    await db.flush()
    return True
