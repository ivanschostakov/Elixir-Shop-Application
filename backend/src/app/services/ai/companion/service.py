import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import config
from src.database.models import AIChat, AIMessage, Attachment, CustomerConsent, User
from src.database.models.ai.companion import AICompanionDialogue, AICompanionEntry, AICompanionEvent, AICompanionOperation, AICompanionPlan, AICompanionProfile, AICompanionReminder, AIProviderResource
from .domain import calculate_nutrition, convert_amount, package_count, parse_package, schedule_events
from .schemas import Action, EntryData, Nutrition, PlanData, ProfileData, Proposal, Settings
from .timezones import normalize_timezone, timezone_info


def now_utc():
    return datetime.now(timezone.utc)


def dump(row):
    if row is None:
        return None
    return {column.name: (value.isoformat() if isinstance(value := getattr(row, column.name), datetime) else value) for column in row.__table__.columns}


async def profile_for(db: AsyncSession, user_id: int):
    return (await db.execute(select(AICompanionProfile).where(AICompanionProfile.user_id == user_id).execution_options(populate_existing=True))).scalar_one_or_none()


async def consent_for(db, user_id):
    return (await db.execute(select(CustomerConsent).where(CustomerConsent.user_id == user_id, CustomerConsent.purpose == "ai_companion", CustomerConsent.channel == "app"))).scalar_one_or_none()


def consent_is_current(consent):
    return bool(consent and consent.is_granted and consent.policy_version == config.AI_COMPANION_CONSENT_VERSION)


async def ensure_default_profile(db, user_id, device_timezone=None):
    """All native customers start in companion mode, without granting consent for them."""
    profile = await profile_for(db, user_id)
    if profile is not None:
        return profile  # Preserve an explicit opt-out and all existing data/settings.
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    profile = await profile_for(db, user_id)
    if profile is None:
        consent = await consent_for(db, user_id)
        settings = Settings(timezone=device_timezone) if device_timezone else Settings()
        profile = AICompanionProfile(user_id=user_id, enabled=consent is None or consent.is_granted, data={}, settings=settings.model_dump(mode="json"), target_history=[])
        db.add(profile)
        await db.flush()
    return profile


async def sync_device_timezone(db, user_id, value):
    """Technical device setting only: never rewrite history, consent or course instants."""
    zone = normalize_timezone(value)
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    profile = await profile_for(db, user_id)
    if profile is None or profile.settings.get("timezone") == zone:
        return False
    profile.settings = {**profile.settings, "timezone": zone}
    # Do not increment the personal-data version: travel does not invalidate
    # pending profile/plan cards. The same user lock serializes settings writes.
    await db.execute(update(AICompanionReminder).where(
        AICompanionReminder.user_id == user_id, AICompanionReminder.kind != "course",
        AICompanionReminder.status == "pending", AICompanionReminder.message_id.is_(None),
        AICompanionReminder.attempts == 0,
    ).values(status="cancelled"))
    await db.flush()
    if profile.enabled and consent_is_current(await consent_for(db, user_id)):
        from .jobs import schedule_recurring
        await schedule_recurring(db, profile, now_utc())
        await db.flush()
    return True


async def require_consent(db, user_id):
    consent = await consent_for(db, user_id)
    if not consent_is_current(consent):
        raise HTTPException(409, "Подтвердите согласие при сохранении личных данных")


async def grant_consent(db, user_id, action):
    if action.consent_version != config.AI_COMPANION_CONSENT_VERSION or not action.adult_confirmed:
        raise HTTPException(422, "Необходимо подтвердить совершеннолетие и актуальное согласие")
    consent = await consent_for(db, user_id)
    if consent is None:
        consent = CustomerConsent(user_id=user_id, purpose="ai_companion", channel="app", source="app")
        db.add(consent)
    consent.is_granted, consent.policy_version, consent.granted_at, consent.revoked_at = True, action.consent_version, now_utc(), None
    consent.last_changed_at = now_utc()
    await db.flush()


async def revoke_consent(db, user_id):
    # Also remember opt-outs made before the first saved personal record.
    consent = await consent_for(db, user_id)
    if consent is None:
        consent = CustomerConsent(user_id=user_id, purpose="ai_companion", channel="app", source="app", policy_version=config.AI_COMPANION_CONSENT_VERSION)
        db.add(consent)
    consent.is_granted, consent.revoked_at, consent.last_changed_at = False, now_utc(), now_utc()
    await db.flush()


async def require_chat_consent(db, user_id, profile):
    consent = await consent_for(db, user_id)
    # An empty default profile can chat and propose drafts immediately. Never
    # reuse previously saved personal state after consent expires or is revoked.
    if consent is None and not profile.data and not profile.target_history:
        return
    if not consent or not consent.is_granted or consent.policy_version != config.AI_COMPANION_CONSENT_VERSION:
        await require_consent(db, user_id)


async def assert_session_active(db, user_id, profile_id):
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    profile = await profile_for(db, user_id)
    if profile is None or profile.id != profile_id or not profile.enabled:
        raise HTTPException(409, "Сопровождение отключено или его данные удалены")
    await require_chat_consent(db, user_id, profile)
    return profile


async def current_plan(db: AsyncSession, user_id: int):
    return (await db.execute(select(AICompanionPlan).where(AICompanionPlan.user_id == user_id, AICompanionPlan.is_current.is_(True)).order_by(AICompanionPlan.id.desc()).limit(1))).scalar_one_or_none()


async def entries_for(db, user_id, start, end, kind=None, limit=200):
    stmt = select(AICompanionEntry).where(AICompanionEntry.user_id == user_id, AICompanionEntry.occurred_at >= start, AICompanionEntry.occurred_at < end)
    if kind:
        stmt = stmt.where(AICompanionEntry.kind == kind)
    return list((await db.execute(stmt.order_by(AICompanionEntry.occurred_at.desc(), AICompanionEntry.id.desc()).limit(limit))).scalars().all())


async def summary_for(db, user_id, start, end):
    # Totals use the complete bounded period, not the UI's paginated entries.
    entries = await entries_for(db, user_id, start, end, limit=10001)
    if len(entries) > 10000:
        raise HTTPException(422, "Слишком много записей; сократите период")
    meals = [e for e in entries if e.kind == "meal"]
    weights = sorted([e for e in entries if e.kind == "weight"], key=lambda e: (e.occurred_at, e.id))
    totals = {key: str(sum((Decimal(str(e.data["nutrition"][key])) for e in meals), Decimal(0))) for key in ("kcal", "protein", "fat", "carbs")}
    events = list((await db.execute(select(AICompanionEvent).where(AICompanionEvent.user_id == user_id, AICompanionEvent.scheduled_at >= start, AICompanionEvent.scheduled_at < end, AICompanionEvent.status != "cancelled"))).scalars().all())
    profile = await profile_for(db, user_id)
    zone = timezone_info(Settings.model_validate(profile.settings if profile else {}).timezone)
    return {"from": start.isoformat(), "to": end.isoformat(), "nutrition": totals, "meals_logged": len(meals), "days_with_meals": len({e.occurred_at.astimezone(zone).date() for e in meals}), "weight_measurements": len(weights), "weight_change_kg": str(Decimal(weights[-1].data["weight_kg"]) - Decimal(weights[0].data["weight_kg"])) if len(weights) > 1 else None, "events": {status: sum(e.status == status for e in events) for status in ("done", "skipped", "pending")}, "coverage_note": "Итоги только по внесённым записям; отсутствие записи не означает отсутствие еды или выполненного действия."}


async def get_state(db, user_id):
    base = {"available": config.AI_COMPANION_ENABLED, "consent_version": config.AI_COMPANION_CONSENT_VERSION, "dialogue_protocol": 2 if config.AI_COMPANION_DIALOGUE_ENABLED else 1}
    if not base["available"]:
        return base
    profile = await profile_for(db, user_id)
    if profile is None:
        return {**base, "consent_required": True, "profile": None, "plan": None, "events": [], "entries": []}
    base["consent_required"] = not consent_is_current(await consent_for(db, user_id))
    settings = Settings.model_validate(profile.settings)
    now = now_utc()
    local = now.astimezone(timezone_info(settings.timezone))
    today = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    tomorrow = (local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).astimezone(timezone.utc)
    events = list((await db.execute(select(AICompanionEvent).where(AICompanionEvent.user_id == user_id, AICompanionEvent.scheduled_at >= today, AICompanionEvent.scheduled_at < now + timedelta(days=7), AICompanionEvent.status != "cancelled").order_by(AICompanionEvent.scheduled_at).limit(100))).scalars().all())
    return {**base, "profile": dump(profile), "plan": dump(await current_plan(db, user_id)), "events": [dump(e) for e in events], "entries": [dump(e) for e in await entries_for(db, user_id, today - timedelta(days=7), tomorrow, limit=100)], "today": await summary_for(db, user_id, today, tomorrow)}


async def context_for(db, user_id):
    state = await get_state(db, user_id)
    if not state.get("profile") or not state["profile"]["enabled"]:
        return None
    profile = state["profile"]
    if state["consent_required"]:
        return {"as_of": now_utc().isoformat(), "profile": {}, "profile_version": profile["version"], "timezone": profile["settings"].get("timezone", "Europe/Moscow"), "active_plan": None, "today": None, "latest_weight": None, "upcoming_events": [], "pending_confirmations": [], "storage_consent_required": True}
    pending_messages = list((await db.execute(select(AIMessage).where(AIMessage.user_id == user_id, AIMessage.is_sensitive.is_(True), AIMessage.sender == "ai").order_by(AIMessage.id.desc()).limit(5))).scalars().all())
    pending = [card for message in pending_messages for card in (message.context_json or {}).get("companion_cards", []) if card.get("state") == "pending"][:3]
    weights = (await db.execute(select(AICompanionEntry).where(AICompanionEntry.user_id == user_id, AICompanionEntry.kind == "weight").order_by(AICompanionEntry.occurred_at.desc(), AICompanionEntry.id.desc()).limit(1))).scalar_one_or_none()
    return {"as_of": now_utc().isoformat(), "pending_confirmations": [{"kind": c["kind"], "summary": c["summary"], "proposal": c["proposal"]} for c in pending], "profile": profile["data"], "profile_version": profile["version"], "timezone": profile["settings"].get("timezone", "Europe/Moscow"), "active_plan": {key: state["plan"][key] for key in ("id", "version", "status")} if state["plan"] else None, "today": state["today"], "latest_weight": dump(weights), "upcoming_events": state["events"][:8]}


async def nutrition_suggestion(db, user_id):
    profile = await profile_for(db, user_id)
    now = now_utc()
    weights = (await db.execute(select(AICompanionEntry).where(AICompanionEntry.user_id == user_id, AICompanionEntry.kind == "weight", AICompanionEntry.occurred_at <= now, AICompanionEntry.occurred_at >= now - timedelta(days=30)).order_by(AICompanionEntry.occurred_at.desc(), AICompanionEntry.id.desc()).limit(1))).scalar_one_or_none()
    if not profile or not weights:
        return {"available": False, "reason": "Заполните профиль и внесите вес за последние 30 дней."}
    try:
        return calculate_nutrition(ProfileData.model_validate(profile.data), Decimal(weights.data["weight_kg"]), config.AI_COMPANION_NUTRITION_RULES_JSON, eligibility_confirmed=Settings.model_validate(profile.settings).nutrition_auto_eligible)
    except (ValueError, KeyError, TypeError):
        return {"available": False, "reason": "Правила питания недоступны. Используйте ручной ввод."}


async def prepare_plan(db, plan, existing=None):
    from src.database.models import Variant
    value = plan.model_copy(deep=True)
    previous = {item.get("variant_id"): item for item in existing.data["items"]} if existing else {}
    for item in value.items:
        if item.variant_id:
            variant = (await db.execute(select(Variant).options(selectinload(Variant.product)).where(Variant.id == item.variant_id, Variant.archived.is_(False)))).scalar_one_or_none()
            if variant is None or variant.product.archived:
                if item.variant_id in previous:
                    item.package_source_name = previous[item.variant_id].get("package_source_name")
                    continue  # Archived catalog rows must not destroy a user's course history.
                raise HTTPException(422, "Вариант товара не найден; сохраните позицию без привязки")
            parsed = parse_package(variant.product.name, variant.name)
            if item.package_amount is None and parsed["known"]:
                item.package_amount, item.package_unit = Decimal(parsed["amount"]), parsed["unit"]
            item.package_source_name = f"{variant.product.name} / {variant.name}"
    return value


async def supply_for(db, user_id, days=30):
    from src.database.models import Variant
    row = await current_plan(db, user_id)
    if row is None or row.status != "active":
        return {"available": False, "reason": "Нет активного курса."}
    plan = PlanData.model_validate(row.data)
    now = now_utc()
    events = list((await db.execute(select(AICompanionEvent).where(AICompanionEvent.plan_id == row.id, AICompanionEvent.scheduled_at >= now, AICompanionEvent.scheduled_at < now + timedelta(days=days), AICompanionEvent.status == "pending"))).scalars().all())
    done = list((await db.execute(select(AICompanionEvent).where(AICompanionEvent.plan_id == row.id, AICompanionEvent.status == "done", AICompanionEvent.occurred_at >= row.created_at))).scalars().all())
    items = []
    for index, item in enumerate(plan.items):
        result = {"name": item.name, "variant_id": item.variant_id, "available": False}
        if not item.package_amount:
            items.append({**result, "reason": "Уточните содержимое упаковки в плане."})
            continue
        if item.home_amount is None:
            items.append({**result, "reason": "Уточните фактический домашний запас; если его нет, укажите 0."})
            continue
        try:
            required = sum((convert_amount(Decimal(e.data["amount"]), e.data["unit"], item.package_unit) for e in events if e.data["item_index"] == index), Decimal(0))
            consumed = sum((convert_amount(Decimal(e.data["amount"]), e.data["unit"], item.package_unit) for e in done if e.data["item_index"] == index), Decimal(0))
            remaining = max(Decimal(0), item.home_amount - consumed)
            count = package_count(required, remaining, item.package_amount)
            balance = remaining
            shortage_at = None
            for event in sorted((e for e in events if e.data["item_index"] == index), key=lambda e: e.scheduled_at):
                balance -= convert_amount(Decimal(event.data["amount"]), event.data["unit"], item.package_unit)
                if balance < 0:
                    shortage_at = event.scheduled_at.isoformat()
                    break
            result["projected_shortage_at"] = shortage_at
            variant = await db.get(Variant, item.variant_id) if item.variant_id else None
            items.append({**result, "available": True, "required": str(required), "home_remaining": str(remaining), "unit": item.package_unit, "packages": count, "price": str(variant.price) if variant and not variant.archived else None, "stock": variant.stock if variant and not variant.archived else None, "estimated_cost": str(variant.price * count) if variant and not variant.archived else None})
        except ValueError as error:
            items.append({**result, "reason": str(error)})
    return {"available": True, "plan_id": row.id, "days": days, "items": items, "note": "Прогноз по расписанию и подтверждённому запасу. Неотмеченные действия могут менять фактический остаток. Доставка и скидки — при оформлении."}


def require_version(actual, expected):
    if expected is None or actual != expected:
        raise HTTPException(409, "Данные изменились. Обновите карточку и подтвердите заново.")


async def cancel_reminders(db, user_id):
    await db.execute(update(AICompanionReminder).where(AICompanionReminder.user_id == user_id, AICompanionReminder.status == "pending").values(status="cancelled"))


async def sync_course_reminders(db, profile):
    await db.execute(update(AICompanionReminder).where(AICompanionReminder.user_id == profile.user_id, AICompanionReminder.kind == "course", AICompanionReminder.status == "pending").values(status="cancelled"))
    settings = Settings.model_validate(profile.settings)
    plan = await current_plan(db, profile.user_id)
    if not profile.enabled or not settings.course_reminders or not plan or plan.status != "active":
        return
    events = list((await db.execute(select(AICompanionEvent).where(AICompanionEvent.plan_id == plan.id, AICompanionEvent.status == "pending", AICompanionEvent.scheduled_at >= now_utc()))).scalars().all())
    for event in events:
        db.add(AICompanionReminder(user_id=profile.user_id, event_id=event.id, kind="course", dedupe_key=f"course:{event.id}:settings:{profile.version}", due_at=event.scheduled_at))


async def apply_action(db: AsyncSession, user_id: int, action: Action, *, allow_commerce=True):
    # Serialize short mutations for this user; do not hold this lock during AI calls.
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    # Consent metadata can disappear after a successful but timed-out first save.
    # It is not a different v2 operation on a retry with the same request key.
    fingerprint = hashlib.sha256(action.model_dump_json(exclude={"consent_version", "adult_confirmed"} if action.kind.startswith("dialogue_") else None).encode()).hexdigest()
    receipt = (await db.execute(select(AICompanionOperation).where(AICompanionOperation.user_id == user_id, AICompanionOperation.request_key == action.request_key))).scalar_one_or_none()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise HTTPException(409, "Ключ запроса уже использован для другого действия")
        return receipt.result
    profile = await profile_for(db, user_id)
    if action.kind == "enable":
        await grant_consent(db, user_id, action)
        if profile is None:
            profile = AICompanionProfile(user_id=user_id, data={}, settings=(action.settings or Settings()).model_dump(mode="json"), target_history=[])
            db.add(profile)
            await db.flush()
        profile.enabled = True
    elif profile is None:
        raise HTTPException(409, "Сначала включите сопровождение")
    elif action.kind == "disable":
        require_version(profile.version, action.expected_version)
        profile.enabled = False
        await cancel_reminders(db, user_id)
        await revoke_consent(db, user_id)
        # The next ordinary chat must not inherit medical context from this session.
        await invalidate_conversation(db, user_id)
    elif not profile.enabled:
        raise HTTPException(403, "Сопровождение отключено")
    else:
        if action.kind not in {"cancel", "delete_entry", "dialogue_cancel", "dialogue_edit"}:
            if action.consent_version is not None:
                await grant_consent(db, user_id, action)
            await require_consent(db, user_id)
        if action.kind.startswith("dialogue_"):
            from .dialogue import apply_card as apply_dialogue_card
            await apply_dialogue_card(db, user_id, action, allow_commerce=allow_commerce)
        elif action.kind in {"confirm", "cancel"}:
            await apply_card(db, user_id, profile, action)
        else:
            await apply_payload(db, user_id, profile, action)
    profile.version += 1
    if action.kind in {"enable", "settings", "plan", "plan_status", "disable", "confirm", "event"}:
        await sync_course_reminders(db, profile)
    result = {"ok": True, "profile_version": profile.version}
    db.add(AICompanionOperation(user_id=user_id, request_key=action.request_key, fingerprint=fingerprint, result=result))
    await db.flush()
    return result


async def apply_payload(db, user_id, profile, action, source_message_id=None):
    if action.kind in {"profile", "settings", "plan", "plan_status", "nutrition"}:
        require_version(profile.version, action.expected_version)
    if action.kind == "profile":
        if action.profile is None:
            raise HTTPException(422, "Нет данных профиля")
        old = ProfileData.model_validate(profile.data)
        new = action.profile
        if old.nutrition != new.nutrition:
            profile.target_history = [*profile.target_history, {"changed_at": now_utc().isoformat(), "previous": old.nutrition.model_dump(mode="json") if old.nutrition else None}]
        profile.data = new.model_dump(mode="json")
    elif action.kind == "nutrition":
        if action.nutrition is None:
            raise HTTPException(422, "Нет значений КБЖУ")
        if action.nutrition_rule_version:
            suggestion = await nutrition_suggestion(db, user_id)
            if not suggestion.get("available") or suggestion["rule_version"] != action.nutrition_rule_version or Nutrition.model_validate(suggestion["nutrition"]) != action.nutrition:
                raise HTTPException(409, "Расчёт изменился. Получите актуальное предложение.")
        new = ProfileData.model_validate(profile.data)
        profile.target_history = [*profile.target_history, {"changed_at": now_utc().isoformat(), "previous": new.nutrition.model_dump(mode="json") if new.nutrition else None}]
        new.nutrition = action.nutrition
        new.nutrition_source = "calculated" if action.nutrition_rule_version else "manual"
        new.nutrition_rule_version = action.nutrition_rule_version
        profile.data = new.model_dump(mode="json")
    elif action.kind == "settings":
        if action.settings is None:
            raise HTTPException(422, "Нет настроек")
        await cancel_reminders(db, user_id)
        profile.settings = action.settings.model_dump(mode="json")
    elif action.kind == "plan":
        if action.plan is None:
            raise HTTPException(422, "Нет плана")
        previous = await current_plan(db, user_id)
        plan = await prepare_plan(db, action.plan, previous)
        events = schedule_events(plan)
        if previous:
            previous.is_current = False
            await db.execute(update(AICompanionEvent).where(AICompanionEvent.plan_id == previous.id, AICompanionEvent.status == "pending", AICompanionEvent.scheduled_at >= now_utc()).values(status="cancelled"))
            await db.flush()
        is_revision = previous is not None and previous.status in {"active", "paused"}
        row = AICompanionPlan(user_id=user_id, course_key=previous.course_key if is_revision else str(uuid4()), version=previous.version + 1 if is_revision else 1, status="active", data=plan.model_dump(mode="json"))
        db.add(row)
        await db.flush()
        for event in events:
            if is_revision and event["scheduled_at"] < now_utc():
                continue
            db.add(AICompanionEvent(user_id=user_id, plan_id=row.id, **event))
    elif action.kind == "plan_status":
        plan = await current_plan(db, user_id)
        if plan is None or action.status not in {"active", "paused", "completed"}:
            raise HTTPException(422, "Некорректное состояние курса")
        if action.status == "active":
            raise HTTPException(422, "Для возобновления подтвердите обновлённое расписание курса")
        plan.status = action.status
        if action.status in {"paused", "completed"}:
            await db.execute(update(AICompanionEvent).where(AICompanionEvent.plan_id == plan.id, AICompanionEvent.scheduled_at >= now_utc(), AICompanionEvent.status == "pending").values(status="cancelled"))
    elif action.kind in {"entry", "delete_entry"}:
        row = await db.get(AICompanionEntry, action.resource_id) if action.resource_id else None
        if action.resource_id and (row is None or row.user_id != user_id):
            raise HTTPException(404, "Запись не найдена")
        if row:
            require_version(row.version, action.expected_version)
        if action.kind == "delete_entry":
            if row is None:
                raise HTTPException(404, "Запись не найдена")
            await db.delete(row)
            return
        if action.entry is None:
            raise HTTPException(422, "Нет данных записи")
        if action.entry.occurred_at > now_utc() + timedelta(minutes=5):
            raise HTTPException(422, "Нельзя отметить фактическую запись в будущем")
        if row is None:
            row = AICompanionEntry(user_id=user_id, kind=action.entry.kind, occurred_at=action.entry.occurred_at, data={}, source="ai_confirmed" if source_message_id else "manual", source_message_id=source_message_id)
            db.add(row)
        else:
            row.version += 1
        row.kind, row.occurred_at, row.data = action.entry.kind, action.entry.occurred_at, action.entry.model_dump(mode="json")
    elif action.kind == "event":
        event = await db.get(AICompanionEvent, action.resource_id) if action.resource_id else None
        if event is None or event.user_id != user_id or event.status == "cancelled":
            raise HTTPException(404, "Событие не найдено")
        require_version(event.version, action.expected_version)
        if action.status not in {"pending", "done", "skipped"}:
            raise HTTPException(422, "Некорректная отметка")
        if event.scheduled_at > now_utc() and action.status == "done":
            raise HTTPException(422, "Нельзя отмечать выполнение будущего события")
        event.status = action.status
        event.occurred_at = now_utc() if action.status == "done" else None
        event.version += 1
        await db.execute(update(AICompanionReminder).where(AICompanionReminder.event_id == event.id, AICompanionReminder.status == "pending").values(status="cancelled"))
    else:
        raise HTTPException(422, "Неподдерживаемое действие")
    await db.flush()


async def attach_proposals(db, user_id, message, proposals, profile, expected_version=None):
    from ..chat_interactive import mint_ai_action_token
    cards = []
    for index, proposal in enumerate(proposals[:3]):
        if proposal.plan:
            proposal.plan = await prepare_plan(db, proposal.plan)
        action_id = f"companion_{index}"
        cards.append({"id": action_id, "kind": proposal.kind, "summary": proposal.summary, "proposal": proposal.model_dump(mode="json"), "profile_version": expected_version if expected_version is not None else profile.version, "state": "pending", "action_token": mint_ai_action_token(user_id=user_id, chat_id=message.chat_id, message_id=message.id, action_id=action_id)})
    context = dict(message.context_json or {})
    context["companion_cards"] = cards
    message.context_json = context
    message.is_sensitive = True


async def apply_card(db, user_id, profile, action):
    from ..chat_interactive import verify_ai_action_token
    try:
        token = verify_ai_action_token(action.action_token or "")
    except ValueError:
        raise HTTPException(401, "Карточка истекла. Запросите актуальные данные.")
    if token.user_id != user_id or token.message_id != action.message_id or token.action_id != action.action_id:
        raise HTTPException(403, "Карточка принадлежит другому запросу")
    message = (await db.execute(select(AIMessage).where(AIMessage.id == action.message_id, AIMessage.user_id == user_id).with_for_update())).scalar_one_or_none()
    if message is None or token.chat_id != message.chat_id:
        raise HTTPException(404, "Карточка не найдена")
    context = json.loads(json.dumps(message.context_json or {}))
    card = next((c for c in context.get("companion_cards", []) if c["id"] == action.action_id), None)
    if not card or card["state"] != "pending":
        raise HTTPException(409, "Действие уже обработано")
    if action.kind == "confirm":
        proposal = Proposal.model_validate(card["proposal"])
        if proposal.kind != "entry":
            require_version(profile.version, card["profile_version"])
        payload = Action(request_key=action.request_key, kind=proposal.kind, expected_version=profile.version, **{proposal.kind: getattr(proposal, proposal.kind)})
        await apply_payload(db, user_id, profile, payload, message.id)
    card["state"] = "confirmed" if action.kind == "confirm" else "cancelled"
    card["action_token"] = None
    message.context_json = context


async def register_resource(db, user_id, kind, external_id):
    if not external_id or str(external_id).startswith("reset:"):
        return
    exists = (await db.execute(select(AIProviderResource.id).where(AIProviderResource.kind == kind, AIProviderResource.external_id == external_id))).scalar_one_or_none()
    if exists is None:
        db.add(AIProviderResource(user_id=user_id, kind=kind, external_id=external_id))
        await db.flush()


async def invalidate_conversation(db, user_id):
    chat = (await db.execute(select(AIChat).where(AIChat.user_id == user_id))).scalar_one_or_none()
    if chat:
        await register_resource(db, user_id, "conversation", chat.conversation_id)
        # A recognizable tombstone forces creation without carrying old context.
        chat.conversation_id = f"reset:{uuid4()}"
        chat.current_tokens = 0


async def erase_companion(db, user_id):
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    profile = await profile_for(db, user_id)
    if profile is None:
        return  # Repeated erasure must not invalidate a new ordinary chat.
    if profile.enabled:
        await invalidate_conversation(db, user_id)
    files = list((await db.execute(select(Attachment).join(AIMessage).where(AIMessage.user_id == user_id, Attachment.is_private.is_(True)))).scalars().all())
    for attachment in files:
        await register_resource(db, user_id, "local_file", str(attachment.relative_path))
    await db.execute(update(AIProviderResource).where(AIProviderResource.user_id == user_id).values(status="pending_delete", next_attempt_at=now_utc() + timedelta(minutes=10)))
    for model in (AICompanionDialogue, AICompanionReminder, AICompanionEvent, AICompanionEntry, AICompanionPlan, AICompanionOperation, AICompanionProfile):
        await db.execute(delete(model).where(model.user_id == user_id))
    # Provider cleanup waits out the maximum in-flight turn (540 s); local records vanish now.
    # Remove actual sensitive message content too, otherwise it can rehydrate memory.
    await db.execute(delete(AIMessage).where(AIMessage.user_id == user_id, AIMessage.is_sensitive.is_(True)))
    await revoke_consent(db, user_id)
