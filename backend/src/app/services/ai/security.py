import ipaddress

from datetime import timedelta
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import (
    AI_CHAT_SUSPICIOUS_ACCOUNTS_PER_IP_DAY,
    AI_CHAT_SUSPICIOUS_MESSAGES_PER_HOUR,
    AI_CHAT_SUSPICIOUS_MESSAGES_PER_MINUTE,
    ufa_now,
)
from src.app.services.admin.alerts import raise_admin_alert
from src.app.services.rate_limit import client_ip_from_request
from src.database.models import AIChatAccessBan, AIChatSecurityEvent, User


def normalized_ai_client_ip(request: Request) -> str:
    raw = client_ip_from_request(request)
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return "unknown"


async def ensure_app_ai_access(
    db: AsyncSession,
    *,
    request: Request,
    user: User,
) -> str:
    ip = normalized_ai_client_ip(request)
    now = ufa_now()
    rows = list((await db.execute(select(AIChatAccessBan).where(
        AIChatAccessBan.is_active.is_(True),
        or_(
            (AIChatAccessBan.ban_type == "account") & (AIChatAccessBan.subject == str(user.id)),
            (AIChatAccessBan.ban_type == "ip") & (AIChatAccessBan.subject == ip),
        ),
    ))).scalars().all())
    active = None
    for row in rows:
        if row.expires_at and row.expires_at <= now:
            row.is_active = False
            row.revoked_at = now
        elif active is None:
            active = row
    if active is not None:
        db.add(AIChatSecurityEvent(
            event_type="access_denied",
            outcome="blocked",
            user_id=user.id,
            ip_address=ip,
            risk_score=100,
            is_suspicious=True,
            risk_reasons=[f"active_{active.ban_type}_ban"],
            details_json={"ban_id": active.id, "ban_type": active.ban_type},
        ))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ai_chat_banned",
                "message": "Доступ к AI-чату ограничен администратором.",
                "ban_type": active.ban_type,
            },
        )
    if rows:
        await db.commit()
    return ip


async def record_app_ai_activity(
    db: AsyncSession,
    *,
    request: Request,
    user: User,
    event_type: str,
    outcome: str = "accepted",
    details: dict[str, Any] | None = None,
) -> AIChatSecurityEvent:
    ip = normalized_ai_client_ip(request)
    now = ufa_now()
    risk_reasons: list[str] = []
    risk_score = 0
    details = dict(details or {})

    if event_type == "message_requested":
        minute_count = int((await db.execute(select(func.count(AIChatSecurityEvent.id)).where(
            AIChatSecurityEvent.event_type == "message_requested",
            AIChatSecurityEvent.user_id == user.id,
            AIChatSecurityEvent.created_at >= now - timedelta(minutes=1),
        ))).scalar_one()) + 1
        hour_count = int((await db.execute(select(func.count(AIChatSecurityEvent.id)).where(
            AIChatSecurityEvent.event_type == "message_requested",
            AIChatSecurityEvent.user_id == user.id,
            AIChatSecurityEvent.created_at >= now - timedelta(hours=1),
        ))).scalar_one()) + 1
        accounts = set((await db.execute(select(distinct(AIChatSecurityEvent.user_id)).where(
            AIChatSecurityEvent.ip_address == ip,
            AIChatSecurityEvent.created_at >= now - timedelta(days=1),
        ))).scalars().all())
        accounts.add(user.id)

        if minute_count >= AI_CHAT_SUSPICIOUS_MESSAGES_PER_MINUTE:
            risk_reasons.append("high_message_rate_minute")
            risk_score += 60
        if hour_count >= AI_CHAT_SUSPICIOUS_MESSAGES_PER_HOUR:
            risk_reasons.append("high_message_rate_hour")
            risk_score += 40
        if len(accounts) >= AI_CHAT_SUSPICIOUS_ACCOUNTS_PER_IP_DAY:
            risk_reasons.append("many_accounts_same_ip")
            risk_score += 50

        details.update({
            "account_messages_last_minute": minute_count,
            "account_messages_last_hour": hour_count,
            "accounts_on_ip_last_day": len(accounts),
        })

    row = AIChatSecurityEvent(
        event_type=event_type[:48],
        outcome=outcome[:32],
        user_id=user.id,
        ip_address=ip,
        risk_score=min(100, risk_score),
        is_suspicious=bool(risk_reasons),
        risk_reasons=risk_reasons,
        details_json=details or None,
    )
    db.add(row)
    await db.flush()

    if risk_reasons:
        await raise_admin_alert(
            db,
            severity="critical" if risk_score >= 80 else "warning",
            source="ai_security",
            code="suspicious_ai_chat_activity",
            title_ru="Подозрительная активность в AI-чате",
            title_en="Suspicious AI chat activity",
            message=(
                f"Пользователь #{user.id}, IP {ip}: "
                + ", ".join(risk_reasons)
            ),
            fingerprint=f"ai-security:app:{user.id}:{':'.join(sorted(risk_reasons))}",
            entity_type="user",
            entity_id=user.id,
            path="/communications?tab=ai&security=1",
            occurred_at=now,
        )
    await db.commit()
    await db.refresh(row)
    return row
