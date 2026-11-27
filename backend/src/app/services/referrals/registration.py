"""First-registration choice; existing accounting customers always keep their program."""

from datetime import datetime, timezone
from decimal import Decimal

from config import LOYALTY_COMPANY_PROMO_CODE, LOYALTY_USE_SETTLEMENT_BALANCE
from fastapi import HTTPException
from sqlalchemy import select

from src.database.models import User
from src.integrations.bitrix_promo import BitrixPromoClient, BitrixPromoError, bitrix_promo_configured
from src.integrations.moysklad.client import get_moysklad_client
from src.integrations.moysklad.client.utils import custom_entity_dictionary_id
from src.integrations.moysklad.idempotency import build_counterparty_external_code, build_sync_id
from src.normalize import optional_str

from .profile import get_or_create_referral_profile, get_referral_profile_by_user_id


async def registration_choice_required(db, *, user):
    profile = await get_referral_profile_by_user_id(db, user.id)
    return bool(profile and user.moysklad_counterparty_id is None
        and (profile.reward_program_snapshot or {}).get("registration_selection_required"))


async def mark_registration_choice_required(db, *, user):
    if user.moysklad_counterparty_id is not None:
        return
    profile = await get_or_create_referral_profile(db, user=user)
    profile.reward_program_selection_source = "registration"
    profile.reward_program_snapshot = {"registration_selection_required": True}
    profile.current_discount_percent = Decimal("0")
    await db.flush()


async def validate_registration_promo(promo):
    if LOYALTY_USE_SETTLEMENT_BALANCE:
        from .ms_codes import resolve_ms_referrer
        return (await resolve_ms_referrer(promo)).code
    if not bitrix_promo_configured():
        raise HTTPException(503, "Проверка промокода временно недоступна.")
    try:
        context = await BitrixPromoClient().lookup(promo)
    except BitrixPromoError as error:
        raise HTTPException(422 if error.status_code < 500 else 503, "Не удалось подтвердить промокод.") from error
    if "is_firm_promo" not in context or "referral_owner_id" not in context:
        raise HTTPException(503, "Проверка программы на сайте временно недоступна.")
    if not (context.get("is_firm_promo") is True or context.get("referral_owner_id")):
        raise HTTPException(422, "Нужен промокод пригласившего или компании.")
    return optional_str(context.get("promo")) or promo


async def record_registration_choice(db, *, user, program, promo_code=None):
    # Older clients retain their existing path. New clients make this choice
    # through the authenticated alert after completing registration.
    if program is None:
        return
    if user.moysklad_counterparty_id is not None:
        return
    promo = (optional_str(promo_code) or LOYALTY_COMPANY_PROMO_CODE) if program == "partner" else None
    if promo:
        promo = await validate_registration_promo(promo)
    profile = await get_or_create_referral_profile(db, user=user)
    if profile.reward_program_selection_source == "moysklad":
        return
    profile.reward_program = program
    profile.reward_program_selected_at = datetime.now(timezone.utc)
    profile.reward_program_selection_source = "registration"
    profile.reward_program_snapshot = {"registration_choice": program, "registration_promo": promo,
        "registration_sync_pending": True, "registration_selection_required": True}
    profile.current_discount_percent = Decimal("0")
    user.promo_code = None  # A pending, unvalidated choice is not an active promo.
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


async def _initial_attributes(client, *, program, promo):
    from src.app.services.benefits.settlement import PROGRAM_ATTRIBUTE_ID, DISCOUNT_ATTRIBUTE_ID, REFERRER_ATTRIBUTE_ID
    attribute = await _attribute_builder(client)
    attrs = [await attribute(PROGRAM_ATTRIBUTE_ID, code=2 if program == "partner" else 1),
             await attribute(DISCOUNT_ATTRIBUTE_ID, number=Decimal(3 if program == "partner" else 0))]
    if promo:
        attrs.append(await attribute(REFERRER_ATTRIBUTE_ID, text=promo))
    return attrs


async def sync_registration_choice(db, *, user):
    if not LOYALTY_USE_SETTLEMENT_BALANCE or not user.is_verified:
        return
    profile = await get_referral_profile_by_user_id(db, user.id)
    if profile is None:
        return
    snapshot = profile.reward_program_snapshot or {}
    if profile.reward_program_selection_source != "registration" or not snapshot.get("registration_sync_pending"):
        return
    client = get_moysklad_client()
    if not client.is_configured():
        raise HTTPException(503, "Не удалось сохранить программу в МойСклад. Повторите позже.")
    # Hold the user row until the deterministic remote create/link is persisted.
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    await db.refresh(user)
    await db.refresh(profile)
    snapshot = profile.reward_program_snapshot or {}
    if not snapshot.get("registration_sync_pending"):
        return
    if user.moysklad_counterparty_id is None:
        from src.app.services.auth.service.counterparty import _link_moysklad_counterparty_by_email
        await _link_moysklad_counterparty_by_email(user, db)
    if user.moysklad_counterparty_id is None:
        # Reacquire after the identity helper's possible commit.
        await db.execute(select(User.id).where(User.id == user.id).with_for_update())
        await db.refresh(user)
        if user.email:
            candidates = await client.get_page("/entity/counterparty", limit=100, search=user.email, expand="contactpersons")
            rows = candidates.get("rows", [])
            if len(rows) >= 100 or any(client._counterparty_email_matches(row, user.email) for row in rows):
                raise HTTPException(409, "Нужна сверка существующего клиента МойСклад. Обратитесь в поддержку.")
    if user.moysklad_counterparty_id is None:
        program = snapshot["registration_choice"]
        promo = snapshot.get("registration_promo") if program == "partner" else None
        if promo:
            promo = await validate_registration_promo(promo)
        attrs = await _initial_attributes(client, program=program, promo=promo)
        external = build_counterparty_external_code(user_id=user.id)
        result = await client.resolve_or_sync_counterparty(existing_counterparty_id=None,
            external_code=external, sync_id=build_sync_id(scope="counterparty", key=external),
            name=" ".join(filter(None, (user.name, user.surname))) or f"App user {user.id}",
            email=user.email, phone=user.phone_number, actual_address=None, initial_attributes=attrs)
        user.moysklad_counterparty_id = result.counterparty_id
        if result.created:
            user.promo_code = promo
    # An existing contact is never updated. Its program wins on the next read.
    profile.reward_program_snapshot = dict(snapshot, registration_sync_pending=False, registration_selection_required=False)
    await db.commit()
