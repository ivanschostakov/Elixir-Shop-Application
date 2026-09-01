import asyncio
import base64
import hashlib
import hmac
import secrets
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    AI_BOT_USAGE_API_TIMEOUT_SECONDS,
    AI_BOT_USAGE_API_TOKEN,
    AI_BOT_USAGE_API_URL,
    AI_BOT_USAGE_BOTS,
    ufa_now,
)
from src.app.modules.admin.schemas import (
    AdminAIUsageBreakdownItem,
    AdminAIUsageDailyPoint,
    AdminAIUsageFunnelItem,
    AdminAIUsageSourceRead,
    AdminAIUsageTopUser,
)
from src.database.models import AIMessage, AIMessageUsage, User, UserEvent
from src.integrations.ai.enums import MessageSender
from .pricing import calculate_openai_text_cost


class AIBotUsageError(RuntimeError):
    pass


def ai_bot_usage_configured() -> bool:
    return bool(AI_BOT_USAGE_API_URL and AI_BOT_USAGE_API_TOKEN)


def _period(days: int) -> tuple[date, date]:
    end = ufa_now().date()
    return end - timedelta(days=days - 1), end


def _date_value(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _percent(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 2) if denominator else 0.0


async def app_ai_usage(db: AsyncSession, *, days: int) -> AdminAIUsageSourceRead:
    start_date, end_date = _period(days)
    start_at = datetime.combine(start_date, datetime.min.time(), tzinfo=ufa_now().tzinfo)

    messages_total, unique_users, conversations, user_messages, assistant_messages = (await db.execute(select(
        func.count(AIMessage.id),
        func.count(distinct(AIMessage.user_id)),
        func.count(distinct(AIMessage.chat_id)),
        func.sum(case((AIMessage.sender == MessageSender.USER, 1), else_=0)),
        func.sum(case((AIMessage.sender == MessageSender.AI, 1), else_=0)),
    ).where(AIMessage.created_at >= start_at))).one()

    successful, input_tokens, cached_tokens, output_tokens = (await db.execute(select(
        func.count(AIMessageUsage.message_id),
        func.coalesce(func.sum(AIMessageUsage.input_tokens), 0),
        func.coalesce(func.sum(AIMessageUsage.cached_input_tokens), 0),
        func.coalesce(func.sum(AIMessageUsage.output_tokens), 0),
    ).join(AIMessage, AIMessage.id == AIMessageUsage.message_id).where(
        AIMessage.created_at >= start_at,
    ))).one()

    message_rows = (await db.execute(select(
        func.date(AIMessage.created_at),
        func.count(distinct(AIMessage.user_id)),
        func.sum(case((AIMessage.sender == MessageSender.USER, 1), else_=0)),
        func.sum(case((AIMessage.sender == MessageSender.AI, 1), else_=0)),
    ).where(AIMessage.created_at >= start_at).group_by(
        func.date(AIMessage.created_at),
    ).order_by(func.date(AIMessage.created_at)))).all()

    usage_rows = (await db.execute(select(
        func.date(AIMessage.created_at),
        func.count(AIMessageUsage.message_id),
        func.coalesce(func.sum(AIMessageUsage.input_tokens), 0),
        func.coalesce(func.sum(AIMessageUsage.cached_input_tokens), 0),
        func.coalesce(func.sum(AIMessageUsage.output_tokens), 0),
    ).join(AIMessage, AIMessage.id == AIMessageUsage.message_id).where(
        AIMessage.created_at >= start_at,
    ).group_by(func.date(AIMessage.created_at)).order_by(func.date(AIMessage.created_at)))).all()

    cost_rows = (await db.execute(select(
        AIMessageUsage.openai_model,
        AIMessageUsage.input_tokens,
        AIMessageUsage.cached_input_tokens,
        AIMessageUsage.output_tokens,
        AIMessage.created_at,
        AIMessage.user_id,
    ).join(AIMessage, AIMessage.id == AIMessageUsage.message_id).where(
        AIMessage.created_at >= start_at,
    ))).all()
    cost_total = Decimal("0")
    cost_by_day: dict[date, Decimal] = {}
    cost_by_model: dict[str, Decimal] = {}
    cost_by_user: dict[int, Decimal] = {}
    unsupported_models: set[str] = set()
    unsupported_days: set[date] = set()
    unsupported_users: set[int] = set()
    for model, row_input, row_cached, row_output, created_at, user_id in cost_rows:
        calculated = calculate_openai_text_cost(
            model=str(model),
            input_tokens=int(row_input or 0),
            cached_input_tokens=int(row_cached or 0),
            output_tokens=int(row_output or 0),
            occurred_at=created_at,
        )
        usage_day = _date_value(created_at)
        if calculated is None:
            unsupported_models.add(str(model))
            unsupported_days.add(usage_day)
            unsupported_users.add(int(user_id))
            continue
        cost_total += calculated.cost_usd
        cost_by_day[usage_day] = cost_by_day.get(usage_day, Decimal("0")) + calculated.cost_usd
        cost_by_model[str(model)] = cost_by_model.get(str(model), Decimal("0")) + calculated.cost_usd
        cost_by_user[int(user_id)] = cost_by_user.get(int(user_id), Decimal("0")) + calculated.cost_usd

    daily: dict[date, AdminAIUsageDailyPoint] = {}
    for raw_day, day_users, day_requests, _day_answers in message_rows:
        day = _date_value(raw_day)
        daily[day] = AdminAIUsageDailyPoint(
            period=day,
            requests=int(day_requests or 0),
            unique_users=int(day_users or 0),
        )
    for raw_day, day_successful, day_input, day_cached, day_output in usage_rows:
        day = _date_value(raw_day)
        point = daily.setdefault(day, AdminAIUsageDailyPoint(period=day))
        point.successful_requests = int(day_successful or 0)
        point.failed_requests = max(point.requests - point.successful_requests, 0)
        point.input_tokens = int(day_input or 0)
        point.cached_input_tokens = int(day_cached or 0)
        point.output_tokens = int(day_output or 0)
        point.total_tokens = point.input_tokens + point.output_tokens
        point.cost_usd = None if day in unsupported_days else float(cost_by_day.get(day, Decimal("0")))
    for point in daily.values():
        if point.failed_requests is None:
            point.failed_requests = max(point.requests - point.successful_requests, 0)
    day = start_date
    while day <= end_date:
        daily.setdefault(day, AdminAIUsageDailyPoint(period=day, failed_requests=0))
        day += timedelta(days=1)

    model_rows = (await db.execute(select(
        AIMessageUsage.openai_model,
        func.count(AIMessageUsage.message_id),
        func.count(distinct(AIMessage.user_id)),
        func.coalesce(func.sum(AIMessageUsage.input_tokens), 0),
        func.coalesce(func.sum(AIMessageUsage.cached_input_tokens), 0),
        func.coalesce(func.sum(AIMessageUsage.output_tokens), 0),
    ).join(AIMessage, AIMessage.id == AIMessageUsage.message_id).where(
        AIMessage.created_at >= start_at,
    ).group_by(AIMessageUsage.openai_model).order_by(func.count(AIMessageUsage.message_id).desc()))).all()
    breakdown = [
        AdminAIUsageBreakdownItem(
            key=str(model),
            label=str(model),
            model=str(model),
            requests=int(requests or 0),
            unique_users=int(users or 0),
            input_tokens=int(row_input or 0),
            cached_input_tokens=int(row_cached or 0),
            output_tokens=int(row_output or 0),
            total_tokens=int(row_input or 0) + int(row_output or 0),
            cost_usd=None if str(model) in unsupported_models else float(cost_by_model.get(str(model), Decimal("0"))),
        )
        for model, requests, users, row_input, row_cached, row_output in model_rows
    ]

    top_user_rows = (await db.execute(select(
        User.id,
        User.name,
        User.surname,
        User.email,
        func.count(AIMessageUsage.message_id),
        func.coalesce(func.sum(AIMessageUsage.input_tokens + AIMessageUsage.output_tokens), 0),
        func.max(AIMessage.created_at),
    ).join(AIMessage, AIMessage.id == AIMessageUsage.message_id).join(
        User, User.id == AIMessage.user_id,
    ).where(AIMessage.created_at >= start_at).group_by(
        User.id, User.name, User.surname, User.email,
    ).order_by(func.count(AIMessageUsage.message_id).desc()).limit(20))).all()
    top_users = [
        AdminAIUsageTopUser(
            account_id=str(user_id),
            label=f"{name} {surname}".strip() or None,
            contact=email,
            requests=int(requests or 0),
            total_tokens=int(tokens or 0),
            cost_usd=None if int(user_id) in unsupported_users else float(cost_by_user.get(int(user_id), Decimal("0"))),
            last_activity_at=last_activity,
        )
        for user_id, name, surname, email, requests, tokens, last_activity in top_user_rows
    ]

    funnel_rows = (await db.execute(select(
        UserEvent.event_name,
        func.count(UserEvent.id),
        func.count(distinct(UserEvent.user_id)),
    ).where(
        UserEvent.event_name.in_((
            "ai_chat_message_sent",
            "ai_recommendation_shown",
            "ai_action_clicked",
            "ai_action_completed",
        )),
        UserEvent.occurred_at >= start_at,
    ).group_by(UserEvent.event_name))).all()
    funnel_map = {name: (int(events or 0), int(users or 0)) for name, events, users in funnel_rows}
    funnel = [
        AdminAIUsageFunnelItem(key=key, label=key, events=funnel_map.get(key, (0, 0))[0], unique_users=funnel_map.get(key, (0, 0))[1])
        for key in ("ai_chat_message_sent", "ai_recommendation_shown", "ai_action_clicked", "ai_action_completed")
    ]

    requests = int(user_messages or 0)
    successful = int(successful or 0)
    input_tokens = int(input_tokens or 0)
    cached_tokens = int(cached_tokens or 0)
    output_tokens = int(output_tokens or 0)
    total_tokens = input_tokens + output_tokens
    return AdminAIUsageSourceRead(
        source="app",
        label="AI-чат приложения",
        start_date=start_date,
        end_date=end_date,
        requests=requests,
        successful_requests=successful,
        failed_requests=max(requests - successful, 0),
        unique_users=int(unique_users or 0),
        conversations=int(conversations or 0),
        user_messages=int(user_messages or 0),
        assistant_messages=int(assistant_messages or 0),
        input_tokens=input_tokens,
        cached_input_tokens=cached_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cache_percent=_percent(cached_tokens, input_tokens),
        average_tokens_per_request=round(total_tokens / successful, 2) if successful else 0.0,
        cost_usd=None if unsupported_models else float(cost_total),
        current_model=breakdown[0].model if len(breakdown) == 1 else None,
        daily=[daily[key] for key in sorted(daily)],
        breakdown=breakdown,
        funnel=funnel,
        top_users=top_users,
        notes=["app_actual_cost_from_exact_usage", "app_failed_requests_inferred"]
        + (["app_cost_has_unsupported_models"] if unsupported_models else []),
    )


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    repeats = (len(data) + len(key) - 1) // len(key)
    stream = (key * repeats)[:len(data)]
    return bytes(left ^ right for left, right in zip(data, stream))


def _bot_auth_headers(token: str) -> dict[str, str]:
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    key = hashlib.sha256(f"{timestamp}:{nonce}:{token}:bot-auth-v1".encode()).digest()
    token_enc = base64.urlsafe_b64encode(_xor_bytes(token.encode(), key)).decode("ascii")
    payload = f"{timestamp}:{nonce}:{token_enc}"
    signature = hmac.new(token.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return {
        "X-Bot-Timestamp": timestamp,
        "X-Bot-Nonce": nonce,
        "X-Bot-Token-Enc": token_enc,
        "X-Bot-Signature": signature,
    }


def _bot_metric(row: dict[str, Any], key: str) -> float:
    aliases = {
        "user_id": ("Айди Телеграм", "user_id"),
        "requests": ("Всего запросов", "total_requests"),
        "input": ("Входящие токены", "input_tokens"),
        "cached": ("Кэшированные входящие токены", "cached_input_tokens"),
        "output": ("Исходящие токены", "output_tokens"),
        "cost": ("Стоимость всего в $", "total_cost_usd"),
    }
    for candidate in aliases[key]:
        if candidate in row:
            try:
                return float(row[candidate] or 0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _aggregate_bot_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "users": len({int(_bot_metric(row, "user_id")) for row in rows if _bot_metric(row, "user_id")}),
        "requests": sum(int(_bot_metric(row, "requests")) for row in rows),
        "input": sum(int(_bot_metric(row, "input")) for row in rows),
        "cached": sum(int(_bot_metric(row, "cached")) for row in rows),
        "output": sum(int(_bot_metric(row, "output")) for row in rows),
        "cost": round(sum(_bot_metric(row, "cost") for row in rows), 4),
    }


def _trend_buckets(start: date, end: date, days: int) -> tuple[str, list[tuple[date, date]]]:
    if days <= 31:
        granularity = "daily"
        step = 1
    elif days <= 120:
        granularity = "weekly"
        step = 7
    else:
        granularity = "monthly"
        step = 0
    buckets: list[tuple[date, date]] = []
    current = start
    while current <= end:
        if granularity == "monthly":
            next_month = date(current.year + (1 if current.month == 12 else 0), 1 if current.month == 12 else current.month + 1, 1)
            bucket_end = min(next_month - timedelta(days=1), end)
        else:
            bucket_end = min(current + timedelta(days=step - 1), end)
        buckets.append((current, bucket_end))
        current = bucket_end + timedelta(days=1)
    return granularity, buckets


async def telegram_ai_usage(*, days: int) -> AdminAIUsageSourceRead:
    start_date, end_date = _period(days)
    if not ai_bot_usage_configured():
        return AdminAIUsageSourceRead(
            source="telegram",
            label="Telegram AI-боты",
            configured=False,
            start_date=start_date,
            end_date=end_date,
            notes=["telegram_integration_not_configured"],
        )

    base_url = str(AI_BOT_USAGE_API_URL).rstrip("/")
    token = str(AI_BOT_USAGE_API_TOKEN)
    semaphore = asyncio.Semaphore(6)

    async with httpx.AsyncClient(timeout=AI_BOT_USAGE_API_TIMEOUT_SECONDS) as client:
        async def report(report_start: date, report_end: date, bot: str | None = None) -> list[dict[str, Any]]:
            async with semaphore:
                try:
                    response = await client.post(
                        f"{base_url}/report",
                        headers=_bot_auth_headers(token),
                        json={"start_date": report_start.isoformat(), "end_date": report_end.isoformat(), "bot": bot},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    rows = payload.get("usages", []) if isinstance(payload, dict) else []
                    return [row for row in rows if isinstance(row, dict)]
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    raise AIBotUsageError("Telegram AI usage backend is unavailable") from exc

        granularity, buckets = _trend_buckets(start_date, end_date, days)
        configured_bots = [bot for bot in AI_BOT_USAGE_BOTS if bot in {"professor", "dose", "new"}]
        total_task = report(start_date, end_date)
        breakdown_tasks = [report(start_date, end_date, bot) for bot in configured_bots]
        trend_tasks = [report(bucket_start, bucket_end) for bucket_start, bucket_end in buckets]
        total_rows, *other_rows = await asyncio.gather(total_task, *breakdown_tasks, *trend_tasks)

    breakdown_rows = other_rows[:len(configured_bots)]
    trend_rows = other_rows[len(configured_bots):]
    total = _aggregate_bot_rows(total_rows)
    labels = {"professor": "Профессор пептидов", "dose": "Расчёт дозировок", "new": "Премиум AI-бот"}
    breakdown: list[AdminAIUsageBreakdownItem] = []
    for bot, rows in zip(configured_bots, breakdown_rows):
        aggregate = _aggregate_bot_rows(rows)
        breakdown.append(AdminAIUsageBreakdownItem(
            key=bot,
            label=labels.get(bot, bot),
            requests=aggregate["requests"],
            unique_users=aggregate["users"],
            input_tokens=aggregate["input"],
            cached_input_tokens=aggregate["cached"],
            output_tokens=aggregate["output"],
            total_tokens=aggregate["input"] + aggregate["output"],
            cost_usd=aggregate["cost"],
        ))
    top_users = sorted((
        AdminAIUsageTopUser(
            account_id=str(int(_bot_metric(row, "user_id"))),
            contact=str(row.get("Номер Телеграм") or row.get("tg_phone") or "") or None,
            requests=int(_bot_metric(row, "requests")),
            total_tokens=int(_bot_metric(row, "input")) + int(_bot_metric(row, "output")),
            cost_usd=round(_bot_metric(row, "cost"), 4),
        )
        for row in total_rows
        if _bot_metric(row, "user_id")
    ), key=lambda item: (item.requests, item.total_tokens), reverse=True)[:20]
    daily: list[AdminAIUsageDailyPoint] = []
    for (bucket_start, bucket_end), rows in zip(buckets, trend_rows):
        aggregate = _aggregate_bot_rows(rows)
        daily.append(AdminAIUsageDailyPoint(
            period=bucket_start,
            period_end=bucket_end if bucket_end != bucket_start else None,
            requests=aggregate["requests"],
            successful_requests=aggregate["requests"],
            unique_users=aggregate["users"],
            input_tokens=aggregate["input"],
            cached_input_tokens=aggregate["cached"],
            output_tokens=aggregate["output"],
            total_tokens=aggregate["input"] + aggregate["output"],
            cost_usd=aggregate["cost"],
        ))
    total_tokens = total["input"] + total["output"]
    return AdminAIUsageSourceRead(
        source="telegram",
        label="Telegram AI-боты",
        start_date=start_date,
        end_date=end_date,
        trend_granularity=granularity,
        requests=total["requests"],
        successful_requests=total["requests"],
        failed_requests=None,
        unique_users=total["users"],
        input_tokens=total["input"],
        cached_input_tokens=total["cached"],
        output_tokens=total["output"],
        total_tokens=total_tokens,
        cache_percent=_percent(total["cached"], total["input"]),
        average_tokens_per_request=round(total_tokens / total["requests"], 2) if total["requests"] else 0.0,
        cost_usd=total["cost"],
        daily=daily,
        breakdown=breakdown,
        top_users=top_users,
        notes=["telegram_failures_not_persisted", "telegram_cost_is_estimated"],
    )


__all__ = ["AIBotUsageError", "ai_bot_usage_configured", "app_ai_usage", "telegram_ai_usage"]
