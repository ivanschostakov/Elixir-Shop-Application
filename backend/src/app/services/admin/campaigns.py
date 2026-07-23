from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, func, select

from config import ufa_now
from src.app.services.push_notifications import send_push_to_user
from src.database import SessionLocal
from src.database.models import AdminPushCampaign, AdminPushCampaignRecipient, NotificationDispatch


MAX_RECIPIENT_ATTEMPTS = 3


async def _campaign_counters(campaign_id: int) -> dict[str, int]:
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(AdminPushCampaignRecipient.status, func.count(AdminPushCampaignRecipient.id))
            .where(AdminPushCampaignRecipient.campaign_id == campaign_id)
            .group_by(AdminPushCampaignRecipient.status)
        )).all()
    counts = {status: int(count) for status, count in rows}
    return {
        "audience": sum(counts.values()),
        "sent": counts.get("sent", 0),
        "skipped": counts.get("skipped", 0),
        "failed": counts.get("error", 0),
        "pending": counts.get("pending", 0),
    }


async def execute_push_campaign(campaign_id: int) -> dict[str, Any]:
    async with SessionLocal() as db:
        campaign = await db.get(AdminPushCampaign, campaign_id)
        if campaign is None:
            raise RuntimeError("Push campaign not found")
        if campaign.status == "canceled":
            return {"campaign_id": campaign_id, "canceled": True}
        if campaign.status == "completed":
            return {"campaign_id": campaign_id, **await _campaign_counters(campaign_id)}
        campaign.status = "running"
        campaign.started_at = campaign.started_at or datetime.now(timezone.utc)
        campaign.error = None
        await db.commit()

    while True:
        async with SessionLocal() as db:
            recipient = (await db.execute(
                select(AdminPushCampaignRecipient)
                .where(
                    AdminPushCampaignRecipient.campaign_id == campaign_id,
                    AdminPushCampaignRecipient.status.in_(("pending", "error")),
                    AdminPushCampaignRecipient.attempts < MAX_RECIPIENT_ATTEMPTS,
                )
                .order_by(
                    case((AdminPushCampaignRecipient.status == "pending", 0), else_=1),
                    AdminPushCampaignRecipient.id,
                )
                .limit(1)
                .with_for_update(skip_locked=True)
            )).scalar_one_or_none()
            if recipient is None:
                break
            campaign = await db.get(AdminPushCampaign, campaign_id)
            if campaign is None or campaign.status == "canceled":
                return {"campaign_id": campaign_id, "canceled": True}
            try:
                sent = await send_push_to_user(
                    db,
                    user_id=recipient.user_id,
                    title=campaign.title,
                    body=campaign.body,
                    data={
                        "type": "admin_campaign",
                        "campaign_id": campaign.id,
                        "deep_link": campaign.deep_link,
                        "utm": campaign.utm_json or {},
                    },
                    channel_id="marketing",
                )
                recipient.attempts += 1
                recipient.error = None
                if sent:
                    recipient.status = "sent"
                    recipient.sent_at = ufa_now()
                    db.add(NotificationDispatch(
                        user_id=recipient.user_id,
                        type="admin_campaign",
                        dedupe_key=f"campaign:{campaign.id}",
                        payload_json={"campaign_id": campaign.id, "deep_link": campaign.deep_link},
                        sent_at=recipient.sent_at,
                    ))
                else:
                    recipient.status = "skipped"
                await db.commit()
            except Exception as error:
                await db.rollback()
                recipient = await db.get(AdminPushCampaignRecipient, recipient.id)
                if recipient is not None:
                    recipient.attempts += 1
                    recipient.status = "error"
                    recipient.error = (str(error) or error.__class__.__name__)[:2000]
                    await db.commit()
                continue

    counters = await _campaign_counters(campaign_id)
    async with SessionLocal() as db:
        campaign = await db.get(AdminPushCampaign, campaign_id)
        if campaign is None:
            raise RuntimeError("Push campaign not found")
        campaign.audience_count = counters["audience"]
        campaign.sent_count = counters["sent"]
        campaign.skipped_count = counters["skipped"]
        campaign.failed_count = counters["failed"]
        campaign.status = "completed"
        campaign.finished_at = datetime.now(timezone.utc)
        campaign.error = None if counters["failed"] == 0 else f"{counters['failed']} recipients failed"
        await db.commit()
    return {"campaign_id": campaign_id, **counters}


async def mark_push_campaign_failed(campaign_id: int, error: str) -> None:
    counters = await _campaign_counters(campaign_id)
    async with SessionLocal() as db:
        campaign = await db.get(AdminPushCampaign, campaign_id)
        if campaign is None or campaign.status in {"completed", "canceled"}:
            return
        campaign.status = "failed"
        campaign.sent_count = counters["sent"]
        campaign.skipped_count = counters["skipped"]
        campaign.failed_count = counters["failed"]
        campaign.error = error[:8000]
        campaign.finished_at = datetime.now(timezone.utc)
        await db.commit()
