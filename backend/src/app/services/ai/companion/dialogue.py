"""Conversational workflow. All writes are scoped, validated and receipted here."""
import copy
import hashlib
import json
import re
from datetime import datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, cast
from sqlalchemy.dialects.postgresql import JSONB

from src.database.models import AIChat, AIMessage, User
from src.database.models.ai.companion import AICompanionDialogue, AICompanionEntry, AICompanionEvent
from src.integrations.ai.enums import MessageSender
from . import service
from .dialogue_schemas import DialogueOperation
from .schemas import Action, Settings, ProfileData
from .timezones import timezone_info

INTRO = "Могу помочь вести ваш текущий курс, отмечать приёмы, питание, вес и самочувствие, напоминать о записях и показывать прогресс. Расскажите, что сейчас принимаете или какую цель хотите отслеживать. Всё можно делать сообщениями — без анкет. После начала учёта буду ежедневно спрашивать о прогрессе в 21:00 по времени телефона; время можно изменить, напоминания — отключить. Я не назначаю препараты и не меняю дозировки."
CONFIRM = {"да", "подтверждаю", "подтвердить", "сохрани", "сохранить", "верно", "всё верно", "все верно"}
CANCEL = {"отмена", "отмени", "не сохраняй", "отменить"}
STOP = {"не напоминай", "выключи напоминания", "отключи напоминания", "не присылай напоминания"}


def normalized(text):
    return re.sub(r"\s+", " ", text.casefold().strip()).rstrip(".! ")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


async def workflow(db, user_id, create=False):
    row = (await db.execute(select(AICompanionDialogue).where(AICompanionDialogue.user_id == user_id))).scalar_one_or_none()
    if row is None and create:
        row = AICompanionDialogue(user_id=user_id, draft={}, focus={})
        db.add(row)
        await db.flush()
    return row


async def chat_for(db, user_id):
    chat = (await db.execute(select(AIChat).where(AIChat.user_id == user_id))).scalar_one_or_none()
    if chat is None:
        chat = AIChat(user_id=user_id, conversation_id=f"reset:{uuid4()}", current_tokens=0, total_tokens=0)
        db.add(chat)
        await db.flush()
    return chat


async def say(db, user_id, text, context=None, sender=MessageSender.AI):
    chat = await chat_for(db, user_id)
    message = AIMessage(user_id=user_id, chat_id=chat.id, sender=sender, text=text, context_json=context or {}, is_sensitive=True)
    db.add(message)
    await db.flush()
    return message


async def introduce(db, user_id):
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    profile = await service.profile_for(db, user_id)
    if not profile or not profile.enabled:
        return
    flow = await workflow(db, user_id, True)
    if flow.introduction_message_id is None:
        message = await say(db, user_id, INTRO)
        flow.introduction_message_id = message.id
        flow.last_hint_at = service.now_utc()
    await db.flush()


async def pending_cards(db, user_id):
    # Query the JSON state, not just the last few messages: a pending course
    # must survive a long unrelated conversation.
    messages = list((await db.execute(select(AIMessage).where(
        AIMessage.user_id == user_id, AIMessage.is_sensitive.is_(True),
        cast(AIMessage.context_json, JSONB).contains({"dialogue_cards": [{"state": "pending"}]}),
    ).order_by(AIMessage.id.desc()).limit(200))).scalars())
    return [(m, c) for m in messages for c in (m.context_json or {}).get("dialogue_cards", []) if c["state"] == "pending"]


async def snapshot(db, user_id):
    flow = await workflow(db, user_id)
    consent = service.consent_is_current(await service.consent_for(db, user_id))
    if not consent:
        return {"protocol": 2, "draft": None, "focus": None, "version": flow.version if flow else 0}
    cards = await pending_cards(db, user_id)
    profile = await service.profile_for(db, user_id)
    return {"protocol": 2, "version": flow.version if flow else 0, "draft": flow.draft if flow else {},
            "focus": flow.focus if flow else {}, "settings": Settings.model_validate(profile.settings).model_dump(mode="json"),
            "pending": [{"message_id": m.id, "card_id": c["id"], "operation": c["operation"]} for m, c in cards[:12]],
            "recent_entries": [service.dump(e) for e in await service.entries_for(db, user_id, service.now_utc() - timedelta(days=7), service.now_utc() + timedelta(minutes=5), limit=20)]}


async def guard_for(db, user_id, kind):
    profile = await service.profile_for(db, user_id)
    if kind in {"plan", "plan_status"}:
        plan = await service.current_plan(db, user_id)
        return digest([plan.id, plan.version, plan.status] if plan else None)
    if kind in {"profile", "nutrition"}:
        return digest(profile.data)
    if kind == "settings":
        return digest({k: v for k, v in profile.settings.items() if k != "timezone"})
    return None


def can_save_immediately(op, user_text):
    if not op.certain or op.kind not in {"entry", "event", "intake"}:
        return False
    if normalized(op.evidence) not in normalized(user_text):
        return False
    # Fail closed for hypothetical, quoted, negated, future and instructional
    # sentences. The model's classification alone is not permission to write.
    if re.search(r"\b(если|допустим|например|завтра|планирую|собираюсь|буду|надо|нужно|не|нельзя|пример|представь|цитата|if|tomorrow|will|not|example|imagine|would|might)\b|[?«»]", user_text, re.I):
        return False
    if op.entry and op.entry.kind == "weight":
        numbers = {Decimal(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", op.evidence)}
        if op.entry.weight_kg not in numbers:
            return False
    return not (op.entry and op.entry.estimated)


async def start_checkins(db, user_id, profile):
    flow = await workflow(db, user_id, True)
    if flow.started_at is not None:
        return
    flow.started_at = service.now_utc()
    settings = Settings.model_validate(profile.settings)
    # Preserve existing schedules. A daily report already provides a daily contact.
    if settings.daily_time is None and settings.checkin_time is None:
        settings.checkin_time = time(21)
        profile.settings = settings.model_dump(mode="json")


def intake_payload(intake, zone, now):
    if intake.local_date > now.astimezone(zone).date():
        raise HTTPException(422, "Нельзя записать будущий приём как состоявшийся")
    if intake.occurred_at is not None:
        if intake.occurred_at > now + timedelta(minutes=5) or intake.occurred_at.astimezone(zone).date() != intake.local_date:
            raise HTTPException(422, "Проверьте фактическую дату и время приёма")
    # A local-day anchor is explicitly NOT an observed time. Render the date
    # and precision metadata, never this anchor as an exact intake timestamp.
    anchor = intake.occurred_at or datetime.combine(intake.local_date, time.min, zone)
    return anchor, {**intake.model_dump(mode="json"), "timezone": str(zone), "time_precision": "exact" if intake.occurred_at else "date"}


async def apply_operation(db, user_id, op, source_message_id, *, allow_commerce=True):
    profile = await service.profile_for(db, user_id)
    before = None
    row = None
    kind = op.kind
    zone = timezone_info(Settings.model_validate(profile.settings).timezone)
    if kind in {"entry", "delete_entry", "intake"}:
        if op.resource_id:
            row = await db.get(AICompanionEntry, op.resource_id)
            if row is None or row.user_id != user_id:
                raise HTTPException(404, "Запись не найдена")
            service.require_version(row.version, op.expected_version)
            if kind == "entry" and row.kind != op.entry.kind or kind == "intake" and row.kind != "intake":
                raise HTTPException(422, "Нельзя менять тип существующей записи")
            before = service.dump(row)
        if kind == "intake":
            anchor, data = intake_payload(op.intake, zone, service.now_utc())
            if row is None:
                row = AICompanionEntry(user_id=user_id, kind="intake", occurred_at=anchor, data=data, source="ai_dialogue", source_message_id=source_message_id)
                db.add(row)
            else:
                row.kind, row.occurred_at, row.data = "intake", anchor, data
                row.version += 1
        else:
            action = Action(request_key=str(uuid4()), kind=kind, resource_id=op.resource_id, expected_version=op.expected_version, entry=op.entry)
            await service.apply_payload(db, user_id, profile, action, source_message_id)
            if kind == "entry" and row is None:
                row = (await db.execute(select(AICompanionEntry).where(AICompanionEntry.user_id == user_id, AICompanionEntry.source_message_id == source_message_id).order_by(AICompanionEntry.id.desc()).limit(1))).scalar_one()
    elif kind == "event":
        row = await db.get(AICompanionEvent, op.resource_id)
        if row is None or row.user_id != user_id or row.status == "cancelled":
            raise HTTPException(404, "Событие не найдено")
        service.require_version(row.version, op.expected_version)
        before = service.dump(row)
        if op.status == "done":
            if op.intake is None:
                raise HTTPException(422, "Уточните фактический день приёма")
            _, actual = intake_payload(op.intake, zone, service.now_utc())
            row.occurred_at = op.intake.occurred_at
            row.data = {**row.data, "actual": actual, "source_message_id": source_message_id}
        else:
            row.occurred_at = None
            row.data = {k: v for k, v in row.data.items() if k != "actual"}
        row.status = op.status
        row.version += 1
    else:
        if kind == "plan" and not allow_commerce:
            existing = await service.current_plan(db, user_id)
            known = {i.get("variant_id") for i in existing.data["items"]} if existing else set()
            if any(i.variant_id and i.variant_id not in known for i in op.plan.items):
                raise HTTPException(403, "На iPhone новые привязки к каталогу недоступны; сохраните название без привязки")
        data = {key: getattr(op, key) for key in ("profile", "plan", "nutrition", "nutrition_rule_version", "settings", "status")}
        if op.settings:
            data["settings"] = op.settings.model_copy(update={"timezone": Settings.model_validate(profile.settings).timezone})
        await service.apply_payload(db, user_id, profile, Action(request_key=str(uuid4()), kind=kind, expected_version=profile.version, **data), source_message_id)
        if kind == "plan":
            # This is disclosed in the confirmation card before saving.
            profile.settings = {**profile.settings, "course_reminders": op.remind_course if op.remind_course is not None else True}
    await db.flush()
    profile.version += 1
    if kind not in {"settings", "delete_entry"}:
        await start_checkins(db, user_id, profile)
    elif kind == "settings":
        # A user's explicit disabled schedule must not be automatically re-enabled.
        flow = await workflow(db, user_id, True)
        flow.started_at = flow.started_at or service.now_utc()
    if kind in {"event", "settings", "plan", "plan_status"}:
        await service.sync_course_reminders(db, profile)
    # The next operation re-reads with populate_existing. Flush both the new
    # version and reminder rows first so a batch cannot reuse a version/key.
    await db.flush()
    if row is not None:
        return {"table": "event" if kind == "event" else "entry", "id": row.id, "before": before,
                "after": None if kind == "delete_entry" else service.dump(row)}
    return None


async def attach_turn(db, user_id, message, turn, user_message, *, allow_commerce, expected_workflow_version, expected_guards=None):
    from ..chat_interactive import mint_ai_action_token
    profile = await service.profile_for(db, user_id)
    flow = await workflow(db, user_id, True)
    if flow.version != expected_workflow_version:
        raise HTTPException(409, "Диалог изменился. Отправьте уточнение ещё раз")
    consent = service.consent_is_current(await service.consent_for(db, user_id))
    cards = []
    operations = [op.model_dump(mode="json") for op in turn.operations]
    if turn.draft and not consent:
        operations.append({"kind": "draft", "summary": "Сохранить черновик и продолжить уточнение", "draft": turn.draft.model_dump(mode="json")})
    for index, raw in enumerate(operations):
        card_id = f"dialogue_{index}"
        card = {"id": card_id, "operation": raw, "kind": raw["kind"], "summary": raw["summary"], "state": "pending",
                "guard": (expected_guards or {}).get(raw["kind"], await guard_for(db, user_id, raw["kind"])), "undo": None,
                "action_token": mint_ai_action_token(user_id=user_id, chat_id=message.chat_id, message_id=message.id, action_id=card_id)}
        op = DialogueOperation.model_validate(raw) if raw["kind"] != "draft" else None
        if op and op.kind in {"profile", "settings"}:
            model = ProfileData if op.kind == "profile" else Settings
            before = model.model_validate(profile.data if op.kind == "profile" else profile.settings).model_dump(mode="json")
            after = getattr(op, op.kind).model_dump(mode="json")
            card["changes"] = [{"parameter": key, "before": before.get(key), "after": value} for key, value in after.items() if value != before.get(key) and key != "timezone"]
        if op and op.plan:
            try:
                current = await service.current_plan(db, user_id)
                if op.remind_course is None:
                    op.remind_course = bool(profile.settings.get("course_reminders")) if current and current.status in {"active", "paused"} else True
                card["summary"] += " Напоминания о событиях курса: " + ("включены." if op.remind_course else "выключены.")
                known = {i.get("variant_id") for i in current.data["items"]} if current else set()
                if not allow_commerce and any(i.variant_id and i.variant_id not in known for i in op.plan.items):
                    raise HTTPException(403, "На iPhone запишите название без новой привязки к каталогу")
                op.plan = await service.prepare_plan(db, op.plan, current)
                card["operation"] = op.model_dump(mode="json")
            except (HTTPException, ValueError) as error:
                card["state"] = "needs_correction"
                card["error"] = str(getattr(error, "detail", "Уточните данные курса"))
        target = flow.focus.get("record")
        if op and target and op.kind in {"entry", "intake", "event", "delete_entry"} and op.resource_id != target["id"]:
            card["state"] = "needs_correction"
            card["error"] = "Уточните исправление исходной записи: новую запись вместо неё не создаю."
        if card["state"] == "pending" and consent and op and can_save_immediately(op, user_message.text):
            try:
                async with db.begin_nested():
                    card["undo"] = await apply_operation(db, user_id, op, user_message.id, allow_commerce=allow_commerce)
                card["state"] = "saved"
            except (HTTPException, ValueError) as error:
                card["state"] = "needs_correction"
                card["error"] = str(getattr(error, "detail", "Проверьте данные записи"))
        cards.append(card)
    # A course + profile/settings/targets is one confirmation and one DB
    # transaction, not a chain of mutually invalidating confirmation buttons.
    grouped = [c for c in cards if c["state"] == "pending" and c["kind"] in {"plan", "profile", "settings", "nutrition", "plan_status"}]
    if len(grouped) > 1 and len({c["kind"] for c in grouped}) == len(grouped):
        group_id = "dialogue_group"
        cards = [c for c in cards if c not in grouped]
        cards.append({"id": group_id, "kind": "batch", "summary": "Подтвердите связанные изменения вместе", "state": "pending", "guard": None, "undo": None,
            "operation": {"kind": "batch", "operations": [c["operation"] for c in grouped]}, "parts": grouped,
            "action_token": mint_ai_action_token(user_id=user_id, chat_id=message.chat_id, message_id=message.id, action_id=group_id)})
    if consent:
        if turn.clear_draft:
            flow.draft = {}
        elif turn.draft:
            flow.draft = {**turn.draft.model_dump(mode="json"), "source_message_id": user_message.id}
    # Editing a pending card replaces its proposal, never applies both versions.
    focus = flow.focus
    if focus.get("card_id") and operations:
        old_message = await db.get(AIMessage, focus["message_id"])
        if old_message and old_message.user_id == user_id:
            old_context = copy.deepcopy(old_message.context_json or {})
            for old in old_context.get("dialogue_cards", []):
                if old["id"] == focus["card_id"] and old["state"] == "pending":
                    old["state"] = "superseded"
            old_message.context_json = old_context
        flow.focus = {}
    flow.version += 1
    context = {**(message.context_json or {}), "dialogue_cards": cards, "source_message_id": user_message.id}
    message.context_json = context
    if re.search(r"\b(сохран[её]н\w*|сохранил\w*|записал\w*|отметил\w*)\b", message.text, re.I):
        message.text = "Результат обработки — в карточках ниже." if cards else "Новых изменений в учёте не выполнено. Уточните, что нужно записать."
    now = service.now_utc()
    if flow.last_hint_at is None:
        flow.last_hint_at = now
    elif not operations and not flow.draft and not flow.focus and now - flow.last_hint_at >= timedelta(days=7) and re.search(r"курс|питан|вес|похуд", user_message.text, re.I):
        message.text += "\n\nЕсли хотите, здесь же можно отмечать курс, питание и вес обычными сообщениями, а итоги открывать кнопками сверху."
        flow.last_hint_at = now
    await db.flush()


async def apply_card(db, user_id, action, *, allow_commerce=True):
    from ..chat_interactive import verify_ai_action_token
    try:
        token = verify_ai_action_token(action.action_token or "")
    except ValueError as error:
        raise HTTPException(401, "Карточка истекла. Запросите актуальную в чате") from error
    if (token.user_id, token.message_id, token.action_id) != (user_id, action.message_id, action.action_id):
        raise HTTPException(403, "Карточка принадлежит другому запросу")
    message = await db.get(AIMessage, action.message_id)
    if message is None or message.user_id != user_id or message.chat_id != token.chat_id:
        raise HTTPException(404, "Карточка не найдена")
    context = copy.deepcopy(message.context_json or {})
    card = next((c for c in context.get("dialogue_cards", []) if c["id"] == action.action_id), None)
    if card is None and action.kind == "dialogue_edit":
        legacy = next((c for c in context.get("companion_cards", []) if c["id"] == action.action_id and c["state"] == "pending"), None)
        if legacy:
            flow = await workflow(db, user_id, True)
            flow.focus = {"message_id": message.id, "card_id": legacy["id"], "operation": legacy["proposal"]}
            flow.version += 1
            legacy["state"] = "cancelled"
            message.context_json = context
            await say(db, user_id, "Что исправить в этой карточке? Напишите изменившиеся данные здесь.")
            await db.flush()
            return
    if card is None:
        raise HTTPException(404, "Карточка не найдена")
    flow = await workflow(db, user_id, True)
    if action.kind == "dialogue_edit":
        if card["state"] not in {"pending", "saved", "needs_correction"}:
            raise HTTPException(409, "Эта карточка больше не актуальна")
        record = None
        if card.get("undo"):
            change = card["undo"]
            model = AICompanionEvent if change["table"] == "event" else AICompanionEntry
            current = await db.get(model, change["id"])
            if current is None or current.user_id != user_id:
                raise HTTPException(409, "Запись уже удалена. Для восстановления используйте отмену удаления")
            record = service.dump(current)
        flow.focus = {"message_id": message.id, "card_id": card["id"], "operation": card["operation"], "record": record}
        await say(db, user_id, "Что исправить? Напишите только изменившиеся данные: например, «время — 20:00». Остальное сохраню.")
    elif action.kind == "dialogue_cancel":
        if card["state"] != "pending":
            raise HTTPException(409, "Действие уже обработано")
        card["state"] = "cancelled"
        if card["kind"] in {"plan", "draft"} or any(part["kind"] == "plan" for part in card.get("parts", [])):
            flow.draft = {}
        flow.focus = {}
    elif action.kind == "dialogue_confirm":
        if card["state"] != "pending":
            raise HTTPException(409, "Действие уже обработано")
        parts = card.get("parts") or [card]
        for part in parts:
            if part["guard"] != await guard_for(db, user_id, part["kind"]):
                raise HTTPException(409, "Данные изменились. Нажмите «Исправить», чтобы обновить карточку")
        for part in parts:
            if part["kind"] == "draft":
                flow.draft = part["operation"]["draft"]
            else:
                op = DialogueOperation.model_validate(part["operation"])
                if op.kind == "settings" and "changes" in part:
                    profile = await service.profile_for(db, user_id)
                    op.settings = Settings.model_validate({**profile.settings, **{c["parameter"]: c["after"] for c in part["changes"]}})
                part["undo"] = await apply_operation(db, user_id, op, context.get("source_message_id", message.id), allow_commerce=allow_commerce)
                if op.kind == "plan":
                    flow.draft = {}
        card["state"] = "saved"
        flow.focus = {}
    elif action.kind == "dialogue_undo":
        if card["state"] != "saved" or not card.get("undo"):
            raise HTTPException(409, "Для этого изменения используйте исправление в диалоге")
        change = card["undo"]
        model = AICompanionEvent if change["table"] == "event" else AICompanionEntry
        row = await db.get(model, change["id"])
        if change["after"] is None:
            # Restoring deleted records reuses their identity; never overwrite a new row.
            if row is not None:
                raise HTTPException(409, "Запись уже восстановлена")
            old = dict(change["before"])
            for key in ("created_at", "updated_at", "occurred_at"):
                if old.get(key): old[key] = datetime.fromisoformat(old[key])
            old["version"] += 1
            row = model(**old)
            db.add(row)
        else:
            if row is None or row.user_id != user_id or row.version != change["after"]["version"] or digest(service.dump(row)) != digest(change["after"]):
                raise HTTPException(409, "Запись уже изменилась; уточните исправление в чате")
            if change["before"] is None:
                await db.delete(row)
            else:
                old = change["before"]
                row.data = old["data"]
                row.occurred_at = datetime.fromisoformat(old["occurred_at"]) if old["occurred_at"] else None
                if change["table"] == "event": row.status = old["status"]
                else: row.kind = old["kind"]
                row.version += 1
        card["state"] = "undone"
        profile = await service.profile_for(db, user_id)
        if change["table"] == "event":
            await db.flush()
            await service.sync_course_reminders(db, profile)
    flow.version += 1
    message.context_json = context
    await db.flush()


async def direct_reply(db, user_id, user_message):
    """Deterministic consent-preserving text confirmation; no model can approve itself."""
    text = normalized(user_message.text)
    if text not in CONFIRM | CANCEL | STOP:
        return None
    if not service.consent_is_current(await service.consent_for(db, user_id)):
        return await say(db, user_id, "Сначала подтвердите согласие на сохранение кнопкой в карточке. Оно запрашивается один раз.")
    profile = await service.profile_for(db, user_id)
    if text in STOP:
        settings = Settings.model_validate(profile.settings)
        settings.course_reminders = settings.supply_reminders = False
        settings.daily_time = settings.weight_time = settings.weekly_time = settings.checkin_time = None
        profile.settings = settings.model_dump(mode="json")
        profile.version += 1
        flow = await workflow(db, user_id, True)
        flow.started_at = flow.started_at or service.now_utc()
        await service.cancel_reminders(db, user_id)
        return await say(db, user_id, "Напоминания отключены. Учёт и история остались.")
    pending = await pending_cards(db, user_id)
    if len(pending) != 1:
        return await say(db, user_id, "Уточните, какую карточку подтвердить или отменить — нажмите кнопку под ней." if pending else "Сейчас нет карточки, ожидающей подтверждения.")
    message, card = pending[0]
    return (message, card, "dialogue_confirm" if text in CONFIRM else "dialogue_cancel")
