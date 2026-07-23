from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.app.services.admin.alerts import raise_admin_alert, resolve_admin_alert
from src.database.models import AdminSlaPolicy, AdminTask, CrmConversation


async def apply_task_sla(
    db: AsyncSession,
    task: AdminTask,
    *,
    origin: datetime | None = None,
) -> AdminSlaPolicy | None:
    policy = (await db.execute(
        select(AdminSlaPolicy).where(
            AdminSlaPolicy.priority == task.priority,
            AdminSlaPolicy.is_enabled.is_(True),
        )
    )).scalar_one_or_none()
    if policy is None:
        task.sla_policy_id = None
        task.response_due_at = None
        task.resolution_due_at = None
        return None
    started_at = origin or task.created_at or ufa_now()
    task.sla_policy_id = policy.id
    task.response_due_at = started_at + timedelta(minutes=policy.response_minutes)
    task.resolution_due_at = started_at + timedelta(minutes=policy.resolution_minutes)
    return policy


async def resolve_task_sla_alert(db: AsyncSession, task_id: int) -> None:
    await resolve_admin_alert(db, fingerprint=f"sla:task:{task_id}")


async def scan_sla_breaches(db: AsyncSession, *, now: datetime | None = None, limit: int = 200) -> int:
    current_time = now or ufa_now()
    rows = list((await db.execute(
        select(AdminTask)
        .where(
            AdminTask.status.in_(("open", "in_progress")),
            AdminTask.sla_breached_at.is_(None),
            or_(
                (AdminTask.status == "open") & (AdminTask.response_due_at.is_not(None)) & (AdminTask.response_due_at < current_time),
                (AdminTask.resolution_due_at.is_not(None)) & (AdminTask.resolution_due_at < current_time),
            ),
        )
        .order_by(AdminTask.resolution_due_at.asc().nullslast(), AdminTask.id.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )).scalars().all())
    for task in rows:
        response_breach = task.status == "open" and task.response_due_at is not None and task.response_due_at < current_time
        breach_kind = "response" if response_breach else "resolution"
        task.sla_breached_at = current_time
        await raise_admin_alert(
            db,
            severity="error" if task.priority in {"urgent", "high"} else "warning",
            source="sla",
            code=f"task_{breach_kind}_breach",
            title_ru="Нарушен SLA задачи",
            title_en="Task SLA breached",
            message=f"Task #{task.id}: {task.title}",
            fingerprint=f"sla:task:{task.id}",
            entity_type="task",
            entity_id=task.id,
            path=f"/tasks?task_id={task.id}",
            occurred_at=current_time,
        )
    conversation_rows = list((await db.execute(
        select(CrmConversation)
        .where(
            CrmConversation.status.in_(("new", "open", "waiting_customer", "waiting_team")),
            CrmConversation.sla_breached_at.is_(None),
            or_(
                (
                    CrmConversation.first_responded_at.is_(None)
                    & CrmConversation.response_due_at.is_not(None)
                    & (CrmConversation.response_due_at < current_time)
                ),
                (
                    CrmConversation.resolution_due_at.is_not(None)
                    & (CrmConversation.resolution_due_at < current_time)
                ),
            ),
        )
        .order_by(CrmConversation.resolution_due_at.asc().nullslast(), CrmConversation.id.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )).scalars().all())
    for conversation in conversation_rows:
        response_breach = (
            conversation.first_responded_at is None
            and conversation.response_due_at is not None
            and conversation.response_due_at < current_time
        )
        breach_kind = "response" if response_breach else "resolution"
        conversation.sla_breached_at = current_time
        await raise_admin_alert(
            db,
            severity="error" if conversation.priority in {"urgent", "high"} else "warning",
            source="sla",
            code=f"support_{breach_kind}_breach",
            title_ru="Нарушен SLA обращения",
            title_en="Support SLA breached",
            message=f"Support conversation #{conversation.id}",
            fingerprint=f"sla:support:{conversation.id}",
            entity_type="support_conversation",
            entity_id=conversation.id,
            path=f"/communications?conversation_id={conversation.id}",
            occurred_at=current_time,
        )
    if rows or conversation_rows:
        await db.commit()
    return len(rows) + len(conversation_rows)
