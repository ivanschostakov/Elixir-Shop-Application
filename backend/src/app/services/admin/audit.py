from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services.admin.permissions import AdminContext
from src.app.services.rate_limit import client_ip_from_request
from src.database.models import AdminAuditLog


async def add_admin_audit(
    db: AsyncSession,
    request: Request,
    context: AdminContext,
    *,
    action: str,
    entity_type: str,
    entity_id: int | str | None,
    before: Any = None,
    after: Any = None,
    details: dict[str, Any] | None = None,
) -> AdminAuditLog:
    row = AdminAuditLog(
        actor_user_id=context.user.id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before_json=jsonable_encoder(before) if before is not None else None,
        after_json=jsonable_encoder(after) if after is not None else None,
        context_json=jsonable_encoder(details or {}),
        ip_address=client_ip_from_request(request),
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        request_id=(request.headers.get("x-request-id") or "")[:120] or None,
    )
    db.add(row)
    await db.flush()
    return row
