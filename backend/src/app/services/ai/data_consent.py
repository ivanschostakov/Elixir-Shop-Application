from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from config import ufa_now
from src.database.models import CustomerConsent, User

AI_DATA_CONSENT_VERSION = "ai-sharing-2026-09-30"


class AIDataConsentPayload(BaseModel):
    granted: bool
    version: str


async def get_ai_data_consent(db, user_id):
    row = (await db.execute(select(CustomerConsent).where(CustomerConsent.user_id == user_id, CustomerConsent.purpose == "ai_data_sharing", CustomerConsent.channel == "app"))).scalar_one_or_none()
    return {"version": AI_DATA_CONSENT_VERSION, "granted": bool(row and row.is_granted and row.policy_version == AI_DATA_CONSENT_VERSION)}


async def require_ai_data_consent(db, user_id):
    if not (await get_ai_data_consent(db, user_id))["granted"]:
        raise HTTPException(403, {"code": "ai_data_consent_required", "message": "Подтвердите передачу данных OpenAI", "version": AI_DATA_CONSENT_VERSION})


async def set_ai_data_consent(db, user_id, payload):
    if payload.granted and payload.version != AI_DATA_CONSENT_VERSION:
        raise HTTPException(409, "Consent version has changed")
    active = (await db.execute(select(User.id).where(User.id == user_id, User.is_active.is_(True)).with_for_update())).scalar_one_or_none()
    if active is None:
        raise HTTPException(401, "Account no longer available")
    row = (await db.execute(select(CustomerConsent).where(CustomerConsent.user_id == user_id, CustomerConsent.purpose == "ai_data_sharing", CustomerConsent.channel == "app"))).scalar_one_or_none()
    if row is None:
        row = CustomerConsent(user_id=user_id, purpose="ai_data_sharing", channel="app", source="app")
        db.add(row)
    row.is_granted = payload.granted
    row.policy_version = AI_DATA_CONSENT_VERSION
    row.last_changed_at = ufa_now()
    if payload.granted:
        row.granted_at, row.revoked_at = row.last_changed_at, None
    else:
        row.revoked_at = row.last_changed_at
    await db.commit()
    return await get_ai_data_consent(db, user_id)
