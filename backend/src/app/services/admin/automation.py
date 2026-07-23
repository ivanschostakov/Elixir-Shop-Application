import hashlib
import json

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from config import ufa_now
from src.app.services.admin.alerts import raise_admin_alert
from src.app.services.admin.jobs import default_max_attempts, enqueue_integration_run
from src.app.services.admin.sla import apply_task_sla
from src.app.services.push_notifications import send_push_to_user
from src.database import SessionLocal
from src.database.models import (
    Admin,
    AdminOrderAutomationExecution,
    AdminOrderAutomationRule,
    AdminTask,
    IntegrationRun,
    NotificationDispatch,
    Order,
)
from src.database.models.orders.history import ORDER_STATUS_CODE_VALUES, OrderStatusCode, build_status_code_clause, get_order_status_code


MAX_RULES_PER_TICK = 50
MAX_ORDERS_PER_RULE = 100
MAX_PREVIEW_ORDERS = 10


class OrderRuleConditions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_codes: list[OrderStatusCode] = Field(default_factory=list, max_length=len(ORDER_STATUS_CODE_VALUES))
    payment_statuses: list[str] = Field(default_factory=list, max_length=12)
    min_age_minutes: int = Field(default=60, ge=5, le=43200)
    missing_delivery: bool = False
    missing_moysklad: bool = False
    only_active: bool = True

    @field_validator("status_codes", "payment_statuses")
    @classmethod
    def normalize_values(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class CreateTaskAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["create_task"]
    assignee_user_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_minutes: int = Field(default=240, ge=5, le=43200)


class QueueOperationAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["queue_operation"]
    operation: Literal["payment_check", "moysklad_sync", "delivery_create"]


class PushCustomerAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["push_customer"]
    title: str = Field(min_length=1, max_length=180)
    body: str = Field(min_length=1, max_length=500)
    deep_link: str | None = Field(default=None, max_length=500)

    @field_validator("deep_link")
    @classmethod
    def internal_deep_link(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if not normalized.startswith("/") or normalized.startswith("//"):
            raise ValueError("Deep link must be an internal app path")
        return normalized


OrderRuleAction = CreateTaskAction | QueueOperationAction | PushCustomerAction


def normalize_order_rule_conditions(value: dict[str, Any]) -> dict[str, Any]:
    return OrderRuleConditions.model_validate(value).model_dump()


def normalize_order_rule_action(value: dict[str, Any]) -> dict[str, Any]:
    action_kind = value.get("kind")
    model: type[CreateTaskAction] | type[QueueOperationAction] | type[PushCustomerAction]
    if action_kind == "create_task":
        model = CreateTaskAction
    elif action_kind == "queue_operation":
        model = QueueOperationAction
    elif action_kind == "push_customer":
        model = PushCustomerAction
    else:
        raise ValueError("Unsupported automation action")
    return model.model_validate(value).model_dump(exclude_none=True)


def default_order_automation_presets(assignee_user_id: int) -> list[dict[str, Any]]:
    return [
        {
            "code": "awaiting_payment_attention",
            "name": "Created order awaiting payment",
            "name_ru": "Созданный заказ ждёт оплаты",
            "name_en": "Created order awaiting payment",
            "description": "Создаёт задачу, если заказ долго находится до оплаты.",
            "description_ru": "Создаёт задачу, если заказ долго находится до оплаты.",
            "description_en": "Creates a staff task when an order waits too long before payment.",
            "priority": 110,
            "conditions_json": {
                "status_codes": ["created", "invoice_sent"],
                "payment_statuses": ["draft", "created", "pending", "error"],
                "min_age_minutes": 180,
                "missing_delivery": False,
                "missing_moysklad": False,
                "only_active": True,
            },
            "action_json": {
                "kind": "create_task",
                "assignee_user_id": assignee_user_id,
                "title": "Проверить оплату заказа {order_code}",
                "description": "Пресет Step 5: заказ долго ждёт оплату. Сначала проверьте контекст, затем решайте, писать ли клиенту.",
                "priority": "normal",
                "due_minutes": 240,
            },
        },
        {
            "code": "paid_missing_delivery",
            "name": "Paid order without delivery",
            "name_ru": "Оплаченный заказ без доставки",
            "name_en": "Paid order without delivery",
            "description": "Создаёт задачу логистике, если оплаченный заказ без созданной доставки.",
            "description_ru": "Создаёт задачу логистике, если оплаченный заказ без созданной доставки.",
            "description_en": "Creates a logistics task when a paid order has no delivery record.",
            "priority": 120,
            "conditions_json": {
                "status_codes": ["paid", "waiting_response", "packaged"],
                "payment_statuses": ["paid"],
                "min_age_minutes": 60,
                "missing_delivery": True,
                "missing_moysklad": False,
                "only_active": True,
            },
            "action_json": {
                "kind": "create_task",
                "assignee_user_id": assignee_user_id,
                "title": "Создать доставку для заказа {order_code}",
                "description": "Пресет Step 5: доставка отсутствует. Проверьте адрес и службу доставки перед ручным восстановлением.",
                "priority": "high",
                "due_minutes": 120,
            },
        },
        {
            "code": "paid_missing_moysklad",
            "name": "Paid order missing in MoySklad",
            "name_ru": "Оплаченный заказ не выгружен в МойСклад",
            "name_en": "Paid order missing in MoySklad",
            "description": "Создаёт задачу, если оплаченный заказ ещё не синхронизирован с МойСклад.",
            "description_ru": "Создаёт задачу, если оплаченный заказ ещё не синхронизирован с МойСклад.",
            "description_en": "Creates a staff task when a paid order is missing in MoySklad.",
            "priority": 130,
            "conditions_json": {
                "status_codes": ["paid", "waiting_response", "packaged", "sent"],
                "payment_statuses": ["paid"],
                "min_age_minutes": 60,
                "missing_delivery": False,
                "missing_moysklad": True,
                "only_active": True,
            },
            "action_json": {
                "kind": "create_task",
                "assignee_user_id": assignee_user_id,
                "title": "Проверить выгрузку МойСклад для {order_code}",
                "description": "Пресет Step 5: заказ оплачен, но идентификатор МойСклад отсутствует.",
                "priority": "high",
                "due_minutes": 180,
            },
        },
        {
            "code": "packaged_not_sent",
            "name": "Packaged order not sent",
            "name_ru": "Упакованный заказ не отправлен",
            "name_en": "Packaged order not sent",
            "description": "Создаёт задачу, если заказ долго остаётся в упаковке.",
            "description_ru": "Создаёт задачу, если заказ долго остаётся в упаковке.",
            "description_en": "Creates a staff task when a packaged order stays unsent too long.",
            "priority": 140,
            "conditions_json": {
                "status_codes": ["packaged"],
                "payment_statuses": ["paid"],
                "min_age_minutes": 720,
                "missing_delivery": False,
                "missing_moysklad": False,
                "only_active": True,
            },
            "action_json": {
                "kind": "create_task",
                "assignee_user_id": assignee_user_id,
                "title": "Отправить или проверить заказ {order_code}",
                "description": "Пресет Step 5: заказ упакован, но долго не перешёл в отправку.",
                "priority": "normal",
                "due_minutes": 240,
            },
        },
    ]


def preset_rule_name(preset: dict[str, Any]) -> str:
    return f"[Preset] {preset['name']}"


async def preview_order_automation_conditions(
    db,
    conditions_json: dict[str, Any],
    *,
    limit: int = MAX_PREVIEW_ORDERS,
) -> tuple[int, list[Order]]:
    conditions = OrderRuleConditions.model_validate(conditions_json)
    now = ufa_now()
    filters = _order_filters(conditions, now=now)
    total = int((await db.execute(select(func.count(Order.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(
        select(Order)
        .options(joinedload(Order.user))
        .where(*filters)
        .order_by(Order.created_at.asc(), Order.id.asc())
        .limit(max(1, min(limit, MAX_PREVIEW_ORDERS)))
    )).scalars().all())
    return total, rows


def _rule_fingerprint(rule: AdminOrderAutomationRule, order: Order) -> str:
    state = {
        "rule": {"conditions": rule.conditions_json, "action": rule.action_json},
        "order": {
            "status_code": get_order_status_code(order),
            "payment_status": order.payment_status,
            "delivery_created": bool(order.delivery_created_at or order.delivery_provider_ref),
            "moysklad_synced": bool(order.moysklad_customerorder_id),
        },
    }
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _order_filters(conditions: OrderRuleConditions, *, now: datetime):
    filters = [Order.created_at <= now - timedelta(minutes=conditions.min_age_minutes)]
    if conditions.only_active:
        filters.extend((Order.is_active.is_(True), Order.is_canceled.is_(False)))
    if conditions.status_codes:
        filters.append(or_(*(build_status_code_clause(Order, code) for code in conditions.status_codes)))
    if conditions.payment_statuses:
        filters.append(Order.payment_status.in_(conditions.payment_statuses))
    if conditions.missing_delivery:
        filters.extend((Order.delivery_created_at.is_(None), Order.delivery_provider_ref.is_(None)))
    if conditions.missing_moysklad:
        filters.append(Order.moysklad_customerorder_id.is_(None))
    return filters


def _operation_details(order: Order, operation: str) -> tuple[str, str]:
    if operation == "payment_check":
        return "intellectmoney", "payment_check"
    if operation == "moysklad_sync":
        return "moysklad", "moysklad_order_sync"
    delivery_service = (order.selected_delivery_service or "").strip().upper()
    if delivery_service == "CDEK":
        return "cdek", "delivery_create"
    if delivery_service == "YANDEX":
        return "yandex_delivery", "delivery_create"
    raise RuntimeError("Order has no supported delivery service")


async def _execute_action(
    db,
    *,
    rule: AdminOrderAutomationRule,
    order: Order,
    action: OrderRuleAction,
    fingerprint: str,
    now: datetime,
) -> tuple[str, dict[str, Any], int | None]:
    if isinstance(action, CreateTaskAction):
        assignee = await db.get(Admin, action.assignee_user_id)
        if assignee is None or not assignee.is_active:
            raise RuntimeError("Automation task assignee is unavailable")
        title = action.title.replace("{order_code}", order.order_code)
        description = action.description.replace("{order_code}", order.order_code) if action.description else None
        task = AdminTask(
            title=title,
            description=description,
            priority=action.priority,
            due_at=now + timedelta(minutes=action.due_minutes),
            customer_user_id=order.user_id,
            order_id=order.id,
            assignee_user_id=action.assignee_user_id,
            created_by_user_id=rule.created_by_user_id,
        )
        await apply_task_sla(db, task, origin=now)
        db.add(task)
        await db.flush()
        return "success", {"task_id": task.id}, None

    if isinstance(action, QueueOperationAction):
        provider, operation = _operation_details(order, action.operation)
        run = IntegrationRun(
            provider=provider,
            operation=operation,
            status="queued",
            requested_by_user_id=rule.created_by_user_id,
            target_type="order",
            target_id=str(order.id),
            attempts=0,
            max_attempts=default_max_attempts(),
            input_json={"automation_rule_id": rule.id},
            idempotency_key=f"auto:{rule.id}:{order.id}:{fingerprint[:32]}",
        )
        db.add(run)
        await db.flush()
        return "queued", {"integration_run_id": run.id, "provider": provider, "operation": operation}, run.id

    sent = await send_push_to_user(
        db,
        user_id=order.user_id,
        title=action.title,
        body=action.body,
        data={
            "type": "order_automation",
            "rule_id": rule.id,
            "order_id": order.id,
            "deep_link": action.deep_link,
        },
        channel_id="marketing",
    )
    if sent:
        db.add(NotificationDispatch(
            user_id=order.user_id,
            type="order_automation",
            dedupe_key=f"rule:{rule.id}:order:{order.id}:{fingerprint}",
            payload_json={"rule_id": rule.id, "order_id": order.id, "deep_link": action.deep_link},
            sent_at=now,
        ))
        return "success", {"sent": True}, None
    return "skipped", {"sent": False, "reason": "no_active_push_token"}, None


async def execute_order_automation_rule(rule_id: int, *, include_disabled: bool = False) -> dict[str, int]:
    counters = {"matched": 0, "executed": 0, "skipped": 0, "failed": 0}
    async with SessionLocal() as db:
        rule = await db.get(AdminOrderAutomationRule, rule_id)
        if rule is None:
            raise RuntimeError("Automation rule not found")
        if not rule.is_enabled and not include_disabled:
            return counters
        try:
            conditions = OrderRuleConditions.model_validate(rule.conditions_json)
            normalized_action = normalize_order_rule_action(rule.action_json)
            action_kind = normalized_action["kind"]
            action: OrderRuleAction
            if action_kind == "create_task":
                action = CreateTaskAction.model_validate(normalized_action)
            elif action_kind == "queue_operation":
                action = QueueOperationAction.model_validate(normalized_action)
            else:
                action = PushCustomerAction.model_validate(normalized_action)
        except Exception as error:
            rule.last_run_at = ufa_now()
            rule.last_error = (str(error) or error.__class__.__name__)[:2000]
            await raise_admin_alert(
                db,
                severity="error",
                source="automation",
                code="invalid_rule",
                title_ru="Ошибка правила автоматизации",
                title_en="Automation rule error",
                message=f"{rule.name}: {rule.last_error}",
                fingerprint=f"automation:rule:{rule.id}",
                entity_type="automation_rule",
                entity_id=rule.id,
                path="/automation",
            )
            await db.commit()
            counters["failed"] = 1
            return counters

        now = ufa_now()
        orders = list((await db.execute(
            select(Order)
            .where(*_order_filters(conditions, now=now))
            .order_by(Order.created_at.asc(), Order.id.asc())
            .limit(MAX_ORDERS_PER_RULE)
        )).scalars().all())
        counters["matched"] = len(orders)
        rule.last_run_at = now
        rule.last_match_count = len(orders)
        rule.last_error = None
        await db.commit()

        for order in orders:
            fingerprint = _rule_fingerprint(rule, order)
            existing = (await db.execute(select(AdminOrderAutomationExecution.id).where(
                AdminOrderAutomationExecution.rule_id == rule.id,
                AdminOrderAutomationExecution.order_id == order.id,
                AdminOrderAutomationExecution.fingerprint == fingerprint,
            ))).scalar_one_or_none()
            if existing is not None:
                counters["skipped"] += 1
                continue

            execution = AdminOrderAutomationExecution(
                rule_id=rule.id,
                order_id=order.id,
                fingerprint=fingerprint,
                action_kind=action.kind,
                status="running",
            )
            try:
                async with db.begin_nested():
                    db.add(execution)
                    await db.flush()
            except IntegrityError:
                counters["skipped"] += 1
                continue
            enqueue_run_id: int | None = None
            try:
                execution.status, execution.result_json, enqueue_run_id = await _execute_action(
                    db,
                    rule=rule,
                    order=order,
                    action=action,
                    fingerprint=fingerprint,
                    now=now,
                )
                counters["executed"] += 1
                if execution.status == "skipped":
                    counters["skipped"] += 1
                await db.commit()
                if enqueue_run_id is not None:
                    try:
                        await enqueue_integration_run(enqueue_run_id)
                    except Exception as error:
                        run = await db.get(IntegrationRun, enqueue_run_id)
                        current_execution = await db.get(AdminOrderAutomationExecution, execution.id)
                        if run is not None:
                            run.status = "error"
                            run.error = f"Failed to enqueue automated operation: {error}"[:8000]
                            run.finished_at = datetime.now(timezone.utc)
                        if current_execution is not None:
                            current_execution.status = "error"
                            current_execution.error = str(error)[:2000]
                        await db.commit()
                        counters["failed"] += 1
            except Exception as error:
                execution.status = "error"
                execution.error = (str(error) or error.__class__.__name__)[:2000]
                await raise_admin_alert(
                    db,
                    severity="error",
                    source="automation",
                    code="rule_execution_failed",
                    title_ru="Не выполнено правило заказа",
                    title_en="Order rule failed",
                    message=f"{rule.name} · {order.order_code}: {execution.error}",
                    fingerprint=f"automation:rule:{rule.id}:order:{order.id}",
                    entity_type="order",
                    entity_id=order.id,
                    path=f"/sales/orders/{order.id}",
                )
                await db.commit()
                counters["failed"] += 1
    return counters


async def process_order_automations_once() -> dict[str, int]:
    async with SessionLocal() as db:
        rule_ids = list((await db.execute(
            select(AdminOrderAutomationRule.id)
            .where(AdminOrderAutomationRule.is_enabled.is_(True))
            .order_by(AdminOrderAutomationRule.priority.asc(), AdminOrderAutomationRule.id.asc())
            .limit(MAX_RULES_PER_TICK)
        )).scalars().all())
    total = {"rules": len(rule_ids), "matched": 0, "executed": 0, "skipped": 0, "failed": 0}
    for rule_id in rule_ids:
        result = await execute_order_automation_rule(int(rule_id))
        for key in ("matched", "executed", "skipped", "failed"):
            total[key] += result[key]
    return total
