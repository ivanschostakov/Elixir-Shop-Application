"""Signed service endpoints; identity and source text come from Telegram, never the model."""
import hashlib
import json
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, text
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.database.models import User, TelegramAIProfile, TelegramAIJournal
from src.database.models.ai.companion import AICompanionProfile, AICompanionEntry
from src.app.services.ai.companion.schemas import StrictModel

router = APIRouter(prefix="/profile")


class Identity(StrictModel):
    telegram_user_id: int = Field(gt=0, le=2**53)


class ProfilePatch(StrictModel):
    goal: Literal["weight_loss", "maintain", "weight_gain", "custom"] | None = None
    goal_detail: str | None = Field(default=None, max_length=1000)
    age: int | None = Field(default=None, ge=1, le=120)
    sex: Literal["male", "female"] | None = None
    height_cm: float | None = Field(default=None, ge=50, le=260)
    current_weight_kg: float | None = Field(default=None, gt=0, le=500)
    target_weight_kg: float | None = Field(default=None, gt=0, le=500)
    activity: str | None = Field(default=None, max_length=500)
    preferences: str | None = Field(default=None, max_length=2000)
    restrictions: str | None = Field(default=None, max_length=2000)


class Update(Identity):
    expected_version: int = Field(ge=0)
    request_key: str = Field(min_length=8, max_length=128)
    source_text: str = Field(min_length=1, max_length=20000)
    evidence: str = Field(min_length=1, max_length=20000)
    patch: ProfilePatch

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.evidence not in self.source_text:
            raise ValueError("Evidence must quote the current user message")
        patch = self.patch.model_dump(exclude_unset=True)
        if not patch:
            raise ValueError("Empty profile update")
        # Reject fabricated numbers even if a model quotes an unrelated real sentence.
        numbers = {float(n.replace(",", ".")) for n in re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?", self.evidence)}
        for field in ("age", "height_cm", "current_weight_kg", "target_weight_kg"):
            value = patch.get(field)
            if value is not None and float(value) not in numbers:
                raise ValueError("Numeric profile values must occur in the quoted message")
        return self


async def legacy_profile(db, telegram_user_id):
    from src.app.services.ai.companion.service import consent_for, consent_is_current
    user = (await db.execute(select(User).where(User.telegram_user_id == telegram_user_id))).scalar_one_or_none()
    if user is None:
        return {}
    if not user.is_active:
        raise HTTPException(403, "Аккаунт отключён")
    saved = (await db.execute(select(AICompanionProfile).where(AICompanionProfile.user_id == user.id))).scalar_one_or_none()
    if saved is None or not saved.enabled or not consent_is_current(await consent_for(db, user.id)):
        return {}
    values = {}
    if saved:
        # Confirmed facts only: never import pending cards, drafts or app eligibility flags.
        for field in ProfilePatch.model_fields:
            value = saved.data.get(field)
            if value is not None:
                try:
                    values.update(ProfilePatch.model_validate({field: value}).model_dump(exclude_unset=True))
                except ValueError:
                    pass
        if "goal_detail" not in values and saved.data.get("custom_goal"):
            try:
                values.update(ProfilePatch(goal_detail=saved.data["custom_goal"]).model_dump(exclude_unset=True))
            except ValueError:
                pass
    weight = (await db.execute(select(AICompanionEntry).where(
        AICompanionEntry.user_id == user.id, AICompanionEntry.kind == "weight",
        AICompanionEntry.occurred_at <= datetime.now(timezone.utc)
    ).order_by(AICompanionEntry.occurred_at.desc(), AICompanionEntry.id.desc()).limit(1))).scalar_one_or_none()
    if weight and weight.data.get("weight_kg") is not None:
        values["current_weight_kg"] = float(weight.data["weight_kg"])
    return values


async def snapshot(db, telegram_user_id):
    row = await db.get(TelegramAIProfile, telegram_user_id)
    if row:
        # Fill absent keys only from an already verified Telegram identity. Local
        # values (including explicit null deletions) win; no phone/name linking.
        inherited = await legacy_profile(db, telegram_user_id)
        return {"profile": {**inherited, **row.data}, "version": row.version}
    return {"profile": await legacy_profile(db, telegram_user_id), "version": 0}


@router.post("/context")
async def context(payload: Identity, db: AsyncSession = Depends(get_db)):
    return await snapshot(db, payload.telegram_user_id)


@router.post("/update")
async def update(payload: Update, db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": -payload.telegram_user_id})
    inherited = await legacy_profile(db, payload.telegram_user_id)
    row = await db.get(TelegramAIProfile, payload.telegram_user_id, populate_existing=True)
    patch = payload.patch.model_dump(exclude_unset=True)
    digest = hashlib.sha256(json.dumps([payload.request_key, patch], sort_keys=True).encode()).hexdigest()
    if row and digest in row.receipts:
        return {"ok": True, "profile": row.data, "version": row.version}
    version = row.version if row else 0
    if payload.expected_version != version:
        raise HTTPException(409, "Профиль уже изменился. Загрузите актуальную версию.")
    if row is None:
        row = TelegramAIProfile(telegram_user_id=payload.telegram_user_id, version=0,
                                data=inherited, receipts=[])
        db.add(row)
    if patch.get("current_weight_kg") is not None:
        db.add(TelegramAIJournal(telegram_user_id=payload.telegram_user_id,
            request_key="weight:" + digest, kind="weight", status="confirmed",
            occurred_at=datetime.now(timezone.utc), data={"weight_kg": patch["current_weight_kg"]}))
    row.data = {**row.data, **patch}
    row.version += 1
    row.receipts = [*row.receipts[-63:], digest]
    await db.commit()
    return {"ok": True, "profile": row.data, "version": row.version}
