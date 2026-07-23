from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any
import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.database.models import (
    AdminPushCampaignRecipient,
    CustomerAttribution,
    CustomerConsent,
    CustomerMarketingProfile,
    User,
    UserDevice,
    UserEvent,
)

log = logging.getLogger(__name__)

EVENT_COUNTER_FIELDS = {
    "product_viewed": "product_views",
    "category_viewed": "category_views",
    "search_submitted": "searches_count",
    "banner_clicked": "banner_clicks",
    "push_opened": "push_opens",
    "push_clicked": "push_clicks",
    "cart_item_added": "cart_adds",
    "cart_item_removed": "cart_removes",
    "checkout_started": "checkout_started",
    "checkout_failed": "checkout_failed",
    "order_created": "orders_created",
    "order_paid": "orders_paid",
}
LEAD_SCORE_WEIGHTS = {
    "app_opened": 1,
    "product_viewed": 2,
    "category_viewed": 1,
    "search_submitted": 2,
    "banner_clicked": 2,
    "push_opened": 2,
    "push_clicked": 4,
    "cart_item_added": 8,
    "cart_item_removed": -2,
    "checkout_started": 12,
    "checkout_failed": 4,
    "order_created": 35,
    "order_paid": 50,
    "ai_chat_message_sent": 2,
    "ai_recommendation_shown": 1,
    "ai_action_clicked": 4,
    "ai_action_completed": 8,
}
ENGAGEMENT_SCORE_WEIGHTS = {
    "app_opened": 1,
    "product_viewed": 1,
    "category_viewed": 1,
    "search_submitted": 2,
    "banner_clicked": 1,
    "push_opened": 1,
    "push_clicked": 2,
    "cart_item_added": 3,
    "cart_item_removed": 1,
    "checkout_started": 4,
    "checkout_failed": 2,
    "order_created": 8,
    "order_paid": 10,
    "ai_chat_message_sent": 2,
    "ai_recommendation_shown": 1,
    "ai_action_clicked": 3,
    "ai_action_completed": 5,
}
ATTRIBUTION_FIELDS = ("source", "medium", "campaign", "content", "term", "referrer", "landing_page")


def _payload_dict(payload: Any, *, exclude_none: bool = False) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="python", exclude_none=exclude_none)
    if isinstance(payload, dict):
        return {key: value for key, value in payload.items() if value is not None or not exclude_none}
    raise TypeError("Expected a Pydantic model or dictionary")


def _lifecycle_stage(profile: CustomerMarketingProfile) -> str:
    if profile.orders_paid >= 2:
        return "repeat_customer"
    if profile.orders_paid >= 1 or profile.orders_created >= 1:
        return "customer"
    if profile.checkout_started >= 1:
        return "high_intent"
    if profile.cart_adds >= 1:
        return "interested"
    if profile.total_events >= 3:
        return "engaged"
    return "new"


async def _record_campaign_engagement(
    session: AsyncSession,
    *,
    user_id: int,
    event_name: str,
    occurred_at: datetime,
    properties: dict[str, Any],
) -> None:
    if event_name not in {"push_opened", "push_clicked"}:
        return
    try:
        campaign_id = int(properties.get("campaign_id"))
    except (TypeError, ValueError):
        return
    recipient = (await session.execute(
        select(AdminPushCampaignRecipient).where(
            AdminPushCampaignRecipient.campaign_id == campaign_id,
            AdminPushCampaignRecipient.user_id == user_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if recipient is None:
        return
    if recipient.opened_at is None or recipient.opened_at > occurred_at:
        recipient.opened_at = occurred_at
    if event_name == "push_clicked" and (recipient.clicked_at is None or recipient.clicked_at > occurred_at):
        recipient.clicked_at = occurred_at


async def get_or_create_marketing_profile(
    session: AsyncSession,
    *,
    user_id: int,
    now: datetime | None = None,
) -> CustomerMarketingProfile:
    observed_at = now or ufa_now()
    await session.execute(
        pg_insert(CustomerMarketingProfile)
        .values(user_id=user_id, first_seen_at=observed_at, last_seen_at=observed_at)
        .on_conflict_do_nothing(index_elements=[CustomerMarketingProfile.user_id])
    )
    profile = (await session.execute(
        select(CustomerMarketingProfile)
        .where(CustomerMarketingProfile.user_id == user_id)
        .with_for_update()
    )).scalar_one()
    return profile


async def upsert_user_device(
    session: AsyncSession,
    *,
    user_id: int,
    payload: Any,
    now: datetime | None = None,
) -> UserDevice:
    data = _payload_dict(payload, exclude_none=True)
    observed_at = now or ufa_now()
    installation_id = data.pop("installation_id")
    metadata = data.pop("metadata", {})
    await session.execute(
        pg_insert(UserDevice)
        .values(
            user_id=user_id,
            installation_id=installation_id,
            first_seen_at=observed_at,
            last_seen_at=observed_at,
            metadata_json=metadata,
            **data,
        )
        .on_conflict_do_nothing(index_elements=[UserDevice.user_id, UserDevice.installation_id])
    )
    device = (await session.execute(
        select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.installation_id == installation_id,
        ).with_for_update()
    )).scalar_one()
    for field, value in data.items():
        setattr(device, field, value)
    device.metadata_json = {**(device.metadata_json or {}), **metadata}
    device.last_seen_at = observed_at
    device.is_active = True
    await session.flush()

    profile = await get_or_create_marketing_profile(session, user_id=user_id, now=observed_at)
    profile.first_seen_at = profile.first_seen_at or observed_at
    profile.last_seen_at = max(filter(None, (profile.last_seen_at, observed_at)), default=observed_at)
    profile.last_platform = device.platform
    profile.last_app_version = device.app_version
    profile.push_permission = device.push_permission
    profile.preferred_language = device.language or profile.preferred_language
    profile.timezone = device.timezone or profile.timezone

    user = await session.get(User, user_id)
    if user is not None and (user.last_active_at is None or user.last_active_at < observed_at):
        user.last_active_at = observed_at

    if device.install_source:
        await update_customer_attribution(
            session,
            user_id=user_id,
            payload={"install_source": device.install_source},
            occurred_at=observed_at,
        )
    return device


async def upsert_customer_consent(
    session: AsyncSession,
    *,
    user_id: int,
    payload: Any,
    now: datetime | None = None,
) -> CustomerConsent:
    data = _payload_dict(payload, exclude_none=True)
    purpose = data.pop("purpose")
    channel = data.pop("channel", "all")
    changed_at = data.pop("changed_at", None) or now or ufa_now()
    await session.execute(
        pg_insert(CustomerConsent)
        .values(user_id=user_id, purpose=purpose, channel=channel)
        .on_conflict_do_nothing(index_elements=[CustomerConsent.user_id, CustomerConsent.purpose, CustomerConsent.channel])
    )
    consent = (await session.execute(
        select(CustomerConsent).where(
            CustomerConsent.user_id == user_id,
            CustomerConsent.purpose == purpose,
            CustomerConsent.channel == channel,
        ).with_for_update()
    )).scalar_one()
    granted = bool(data.pop("is_granted"))
    consent.is_granted = granted
    consent.source = data.pop("source", "app")
    consent.policy_version = data.pop("policy_version", consent.policy_version)
    consent.last_changed_at = changed_at
    consent.granted_at = changed_at if granted else consent.granted_at
    consent.revoked_at = None if granted else changed_at
    await session.flush()
    return consent


async def update_customer_attribution(
    session: AsyncSession,
    *,
    user_id: int,
    payload: Any,
    occurred_at: datetime,
) -> CustomerAttribution | None:
    data = _payload_dict(payload, exclude_none=True)
    if not data:
        return None
    await session.execute(
        pg_insert(CustomerAttribution)
        .values(user_id=user_id)
        .on_conflict_do_nothing(index_elements=[CustomerAttribution.user_id])
    )
    attribution = (await session.execute(
        select(CustomerAttribution)
        .where(CustomerAttribution.user_id == user_id)
        .with_for_update()
    )).scalar_one()
    has_touch = any(data.get(field) for field in ATTRIBUTION_FIELDS)
    if has_touch and attribution.first_touch_at is None:
        for field in ATTRIBUTION_FIELDS:
            setattr(attribution, f"first_{field}", data.get(field))
        attribution.first_touch_at = occurred_at
    if has_touch:
        for field in ATTRIBUTION_FIELDS:
            if field in data:
                setattr(attribution, f"last_{field}", data[field])
        attribution.last_touch_at = occurred_at
    if data.get("install_source"):
        attribution.install_source = data["install_source"]
    await session.flush()
    return attribution


async def record_customer_event(
    session: AsyncSession,
    *,
    user_id: int,
    event_name: str,
    occurred_at: datetime | None = None,
    event_id: uuid.UUID | None = None,
    device: UserDevice | None = None,
    source: str = "api",
    session_id: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    properties: dict[str, Any] | None = None,
    attribution: Any | None = None,
    profile: CustomerMarketingProfile | None = None,
    known_event_ids: set[uuid.UUID] | None = None,
    commit: bool = False,
) -> UserEvent | None:
    observed_at = occurred_at or ufa_now()
    resolved_event_id = event_id or uuid.uuid4()
    if known_event_ids is not None:
        if resolved_event_id in known_event_ids:
            return None
    elif (await session.execute(select(UserEvent.id).where(UserEvent.event_id == resolved_event_id))).scalar_one_or_none() is not None:
        return None

    event_database_id = (await session.execute(
        pg_insert(UserEvent)
        .values(
            event_id=resolved_event_id,
            user_id=user_id,
            device_id=device.id if device else None,
            event_name=event_name,
            source=source,
            session_id=session_id,
            entity_type=entity_type,
            entity_id=entity_id,
            occurred_at=observed_at,
            properties_json=properties or {},
            attribution_json=_payload_dict(attribution, exclude_none=True) if attribution is not None else {},
        )
        .on_conflict_do_nothing(index_elements=[UserEvent.event_id])
        .returning(UserEvent.id)
    )).scalar_one_or_none()
    if event_database_id is None:
        if known_event_ids is not None:
            known_event_ids.add(resolved_event_id)
        return None
    event = await session.get(UserEvent, event_database_id)
    if event is None:
        raise RuntimeError("Inserted customer event could not be loaded")
    await _record_campaign_engagement(
        session,
        user_id=user_id,
        event_name=event_name,
        occurred_at=observed_at,
        properties=properties or {},
    )

    profile = profile or await get_or_create_marketing_profile(session, user_id=user_id, now=observed_at)
    profile.first_seen_at = profile.first_seen_at or observed_at
    if profile.last_seen_at is None or profile.last_seen_at < observed_at:
        profile.last_seen_at = observed_at
        profile.last_event_name = event_name
    profile.total_events += 1
    counter_field = EVENT_COUNTER_FIELDS.get(event_name)
    if counter_field:
        setattr(profile, counter_field, getattr(profile, counter_field) + 1)
    profile.lead_score = min(100, max(0, profile.lead_score + LEAD_SCORE_WEIGHTS.get(event_name, 0)))
    profile.engagement_score = min(1000, max(0, profile.engagement_score + ENGAGEMENT_SCORE_WEIGHTS.get(event_name, 0)))
    if event_name == "order_paid":
        profile.last_purchase_at = observed_at

    if device is not None:
        device.last_seen_at = max(device.last_seen_at, observed_at)
        profile.last_platform = device.platform
        profile.last_app_version = device.app_version
        profile.push_permission = device.push_permission
        profile.preferred_language = device.language or profile.preferred_language
        profile.timezone = device.timezone or profile.timezone
    if event_name == "app_opened":
        if device is None or not session_id or device.last_session_id != session_id:
            profile.sessions_count += 1
        if device is not None and (not session_id or device.last_session_id != session_id):
            device.sessions_count += 1
            device.last_session_id = session_id
    profile.lifecycle_stage = _lifecycle_stage(profile)

    if attribution is not None:
        await update_customer_attribution(
            session,
            user_id=user_id,
            payload=attribution,
            occurred_at=observed_at,
        )
    user = await session.get(User, user_id)
    if user is not None and (user.last_active_at is None or user.last_active_at < observed_at):
        user.last_active_at = observed_at

    await session.flush()
    if known_event_ids is not None:
        known_event_ids.add(resolved_event_id)
    if commit:
        await session.commit()
    return event


async def record_customer_event_safe(
    session: AsyncSession,
    **kwargs: Any,
) -> UserEvent | None:
    commit = bool(kwargs.pop("commit", False))
    try:
        async with session.begin_nested():
            event = await record_customer_event(session, commit=False, **kwargs)
        if commit:
            await session.commit()
        return event
    except Exception:
        log.exception(
            "Customer event tracking failed user_id=%s event_name=%s",
            kwargs.get("user_id"),
            kwargs.get("event_name"),
        )
        if commit:
            await session.rollback()
        return None


async def ingest_customer_intelligence(
    session: AsyncSession,
    *,
    user_id: int,
    payload: Any,
) -> dict[str, Any]:
    now = ufa_now()
    device = await upsert_user_device(session, user_id=user_id, payload=payload.device, now=now) if payload.device else None
    updated_consents = 0
    for consent_payload in payload.consents:
        await upsert_customer_consent(session, user_id=user_id, payload=consent_payload, now=now)
        updated_consents += 1

    profile = await get_or_create_marketing_profile(session, user_id=user_id, now=now)
    requested_ids = {event.event_id for event in payload.events}
    known_ids = set((await session.execute(
        select(UserEvent.event_id).where(UserEvent.event_id.in_(requested_ids))
    )).scalars().all()) if requested_ids else set()
    duplicates = len(known_ids)
    accepted = 0
    for event_payload in payload.events:
        was_known = event_payload.event_id in known_ids
        event = await record_customer_event(
            session,
            user_id=user_id,
            event_name=event_payload.name,
            occurred_at=event_payload.occurred_at,
            event_id=event_payload.event_id,
            device=device,
            source=event_payload.source,
            session_id=event_payload.session_id,
            entity_type=event_payload.entity_type,
            entity_id=event_payload.entity_id,
            properties=event_payload.properties,
            attribution=event_payload.attribution,
            profile=profile,
            known_event_ids=known_ids,
        )
        if event is not None:
            accepted += 1
        elif not was_known:
            duplicates += 1
    await session.commit()
    await session.refresh(profile)
    return {
        "device_id": device.id if device else None,
        "accepted_events": accepted,
        "duplicate_events": duplicates,
        "updated_consents": updated_consents,
        "profile_updated_at": profile.updated_at,
    }


async def delete_expired_customer_events(
    session: AsyncSession,
    *,
    retention_days: int,
    batch_size: int = 5000,
    max_batches: int = 20,
) -> int:
    if retention_days < 1:
        raise ValueError("Customer event retention must be at least one day")
    cutoff = ufa_now() - timedelta(days=retention_days)
    deleted_count = 0
    for _ in range(max_batches):
        expired_ids = select(UserEvent.id).where(
            UserEvent.received_at < cutoff,
        ).order_by(UserEvent.id).limit(batch_size)
        deleted_ids = list((await session.execute(
            delete(UserEvent)
            .where(UserEvent.id.in_(expired_ids))
            .returning(UserEvent.id)
        )).scalars().all())
        await session.commit()
        deleted_count += len(deleted_ids)
        if len(deleted_ids) < batch_size:
            break
    return deleted_count


__all__ = [
    "EVENT_COUNTER_FIELDS",
    "delete_expired_customer_events",
    "ingest_customer_intelligence",
    "record_customer_event",
    "record_customer_event_safe",
    "upsert_customer_consent",
    "upsert_user_device",
]
