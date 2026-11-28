"""Provision the mobile registration bonus without modifying existing accounting cards."""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

from config import LOYALTY_USE_SETTLEMENT_BALANCE
from fastapi import HTTPException
from sqlalchemy import select

from src.database.models import User
from src.integrations.moysklad.client import get_moysklad_client
from src.integrations.moysklad.client.utils import custom_entity_dictionary_id
from src.integrations.moysklad.idempotency import build_counterparty_external_code, build_sync_id
from src.integrations.moysklad.identity import CounterpartyReviewRequired
from src.app.services.counterparty_review import queue_counterparty_review
from src.normalize import coerce_uuid, normalize_email, normalize_phone

from .profile import get_or_create_referral_profile, get_referral_profile_by_user_id


logger = logging.getLogger(__name__)
AUTH_PROVISION_TIMEOUT_SECONDS = 5


def _pending(profile):
    if profile is None or profile.reward_program_selection_source != "registration":
        return False
    snapshot = profile.reward_program_snapshot or {}
    return bool(snapshot.get("registration_selection_required") or snapshot.get("registration_sync_pending"))


def _mark_pending_bonus(profile):
    profile.reward_program_selection_source = "registration"
    profile.reward_program_snapshot = dict(profile.reward_program_snapshot or {},
        registration_choice="bonus", registration_promo=None,
        registration_sync_pending=True, registration_selection_required=False)


def _apply_bonus(profile, user):
    if profile.reward_program != "bonus" or profile.reward_program_selected_at is None:
        profile.reward_program_selected_at = datetime.now(timezone.utc)
    profile.reward_program = "bonus"
    profile.current_discount_percent = Decimal("0")
    user.promo_code = None


async def queue_registration_bonus(db, *, user):
    if user.moysklad_counterparty_id is not None:
        return
    profile = await get_or_create_referral_profile(db, user=user)
    if profile.reward_program_selection_source not in {None, "system_default"} and not _pending(profile):
        return
    _mark_pending_bonus(profile)
    await db.flush()


async def _attribute_builder(client):
    from src.app.services.benefits.settlement import PROGRAM_NAMES
    rows = await client.get_all("/entity/counterparty/metadata/attributes")
    metadata = {row.get("id"): row for row in rows}

    async def attribute(attr_id, *, code=None, number=None, text=None):
        row = metadata.get(attr_id) or {}
        if not row.get("meta"):
            raise RuntimeError("Missing MoySklad loyalty attribute metadata")
        if row.get("type") == "customentity":
            dictionary_id = custom_entity_dictionary_id(row)
            if dictionary_id is None:
                raise RuntimeError("Missing MoySklad loyalty dictionary")
            choices = await client.get_all(f"/entity/customentity/{dictionary_id}")
            def matches(choice):
                name = str(choice.get("name", "")).strip().casefold()
                if code is not None:
                    return PROGRAM_NAMES.get(name) == code
                try:
                    return Decimal(name.removesuffix("%").strip().replace(",", ".")) == number
                except ArithmeticError:
                    return False
            choices = [choice for choice in choices if matches(choice)]
            if len(choices) != 1 or not choices[0].get("meta"):
                raise RuntimeError("Ambiguous MoySklad loyalty dictionary value")
            value = {"meta": choices[0]["meta"]}
        elif text is not None and row.get("type") in {"string", "text"}:
            value = text
        elif number is not None and row.get("type") in {"double", "long", "string"}:
            value = str(number) if row["type"] == "string" else int(number)
        else:
            raise RuntimeError("Unsupported MoySklad loyalty attribute type")
        return {"meta": row["meta"], "value": value}

    return attribute


async def zero_discount_attribute(client):
    from src.app.services.benefits.settlement import DISCOUNT_ATTRIBUTE_ID
    attribute = await _attribute_builder(client)
    return await attribute(DISCOUNT_ATTRIBUTE_ID, number=Decimal(0))


async def _initial_attributes(client):
    from src.app.services.benefits.settlement import PROGRAM_ATTRIBUTE_ID, DISCOUNT_ATTRIBUTE_ID
    attribute = await _attribute_builder(client)
    return [await attribute(PROGRAM_ATTRIBUTE_ID, code=1),
            await attribute(DISCOUNT_ATTRIBUTE_ID, number=Decimal(0))]


async def _registration_counterparty(user):
    client = get_moysklad_client()
    if not client.is_configured():
        raise HTTPException(503, "Не удалось сохранить программу в МойСклад. Повторите позже.")
    email, phone = normalize_email(user.email), normalize_phone(user.phone_number)
    external = build_counterparty_external_code(user_id=user.id)
    by_email = await client.get_counterparty_by_email(email) if email else None
    by_phone = await client.get_counterparty_by_phone(phone) if phone else None
    if by_email or by_phone:
        card = by_email or by_phone
        cid = coerce_uuid(card.get("id"))
        phone_conflict = (phone and normalize_phone(card.get("phone"))
                          and not client._counterparty_phone_matches(card, phone))
        if (cid and not phone_conflict and (not by_phone or card.get("id") == by_phone.get("id"))
                and (by_email or card.get("externalCode") == external)):
            return cid, False
        raise CounterpartyReviewRequired("email и телефону", [by_email, by_phone])

    result = await client.resolve_or_sync_counterparty(existing_counterparty_id=None,
        external_code=external, sync_id=build_sync_id(scope="counterparty", key=external),
        name=" ".join(filter(None, (user.name, user.surname))) or f"App user {user.id}",
        email=email, phone=phone, actual_address=None,
        initial_attributes=await _initial_attributes(client))
    return result.counterparty_id, result.created


async def sync_registration_choice(db, *, user, best_effort=False):
    if not user.is_verified:
        return
    profile = await get_referral_profile_by_user_id(db, user.id)
    if not _pending(profile):
        return
    # NO KEY UPDATE serializes retries but permits FK inserts for a concurrent login.
    locked = await db.scalar(select(User.id).where(User.id == user.id)
        .with_for_update(key_share=True, skip_locked=best_effort))
    if locked is None:
        return
    await db.refresh(user)
    await db.refresh(profile)
    if not user.is_verified or not _pending(profile):
        return
    if user.moysklad_counterparty_id is None:
        _mark_pending_bonus(profile)
        if LOYALTY_USE_SETTLEMENT_BALANCE:
            try:
                async with asyncio.timeout(AUTH_PROVISION_TIMEOUT_SECONDS if best_effort else None):
                    cid, created = await _registration_counterparty(user)
            except CounterpartyReviewRequired as exc:
                await queue_counterparty_review(exc, user_id=user.id)
                if not best_effort:
                    raise
                await db.commit()
                return
            except Exception:
                if not best_effort:
                    raise
                logger.exception("Deferring registration bonus sync user_id=%s", user.id)
                _apply_bonus(profile, user)
                await db.commit()
                return
            user.moysklad_counterparty_id = cid
            if created:
                _apply_bonus(profile, user)
        else:
            _apply_bonus(profile, user)
    profile.reward_program_snapshot = dict(profile.reward_program_snapshot,
        registration_sync_pending=False, registration_selection_required=False)
    await db.commit()
