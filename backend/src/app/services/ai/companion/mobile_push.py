"""Durable native notifications. Callers hold the same per-user lock as diary writes."""
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.database.models import UserPushToken
from src.database.models.ai.companion import AICompanionEntry, AICompanionReminder
from . import service
from .jobs import local_due, save_reminder_message
from .meals import eating_habits
from .push_rules import MINUTE, Notice, nutrition_notices, plan_signature, program_complete, wellbeing_notices, workout_notices
from .schemas import Settings, WorkoutPlan
from .timezones import timezone_info


async def candidates(db, profile, now):
    settings = Settings.model_validate(profile.settings)
    topics = set(settings.mobile.topics)
    if settings.notifications_paused or (not topics and not settings.meal_reminders):
        return {}
    zone = timezone_info(settings.timezone)
    day = now.astimezone(zone).date()
    start = datetime.combine(day - timedelta(days=1), time.min, zone)
    rows = list((await db.scalars(select(AICompanionEntry).where(
        AICompanionEntry.user_id == profile.user_id, AICompanionEntry.occurred_at >= start,
        AICompanionEntry.occurred_at <= now, AICompanionEntry.kind.in_(["meal", "water", "wellbeing", "workout"])
    ).order_by(AICompanionEntry.occurred_at, AICompanionEntry.id))).all())
    def clock(t):
        return local_due(day, t, zone)
    notices = []
    if topics.intersection({"nutrition", "meal_balance", "water"}) or settings.meal_reminders:
        habits = {}
        if "nutrition" in topics or settings.meal_reminders:
            history = await service.entries_for(db, profile.user_id, now - timedelta(days=28), now, "meal", limit=10000)
            habits = eating_habits(history, zone, day)
        notices.extend(nutrition_notices(profile, settings, now, zone, rows, habits, clock))
    notices.extend(workout_notices(profile, settings, now, zone, rows, clock))
    yesterday_bed = False
    if "sleep" in topics:
        yesterday_bed = await db.scalar(select(AICompanionReminder.id).where(AICompanionReminder.user_id == profile.user_id,
            AICompanionReminder.dedupe_key == f"bed:{day-timedelta(days=1)}", AICompanionReminder.status == "sent"))
    notices.extend(wellbeing_notices(settings, now, zone, rows, clock, yesterday_bed))
    plan = WorkoutPlan.model_validate(profile.data["workout_plan"]) if profile.data.get("workout_plan") else None
    if "program" in topics and plan and plan.end_date:
        recent = [r for r in rows if r.kind == "workout" and r.data["workout"]["status"] == "completed" and r.data["workout"].get("scheduled_date")
                  and any(b.key == r.data["workout"].get("plan_day_key") for b in plan.scheduled(date.fromisoformat(r.data["workout"]["scheduled_date"])))]
        if recent:
            dates = select(AICompanionEntry.data["workout"]["scheduled_date"].as_string(), AICompanionEntry.data["workout"]["plan_day_key"].as_string()).where(
                AICompanionEntry.user_id == profile.user_id, AICompanionEntry.kind == "workout",
                AICompanionEntry.data["workout"]["status"].as_string() == "completed",
                AICompanionEntry.data["workout"]["scheduled_date"].as_string().between(plan.start_date.isoformat(), plan.end_date.isoformat()))
            pairs = {(date.fromisoformat(d), k) for d, k in (await db.execute(dates)).all() if d and k}
            if program_complete(plan, pairs):
                signature = plan_signature(plan)
                finished = max((datetime.fromisoformat(r.data["workout"]["finished_at"]) if r.data["workout"].get("finished_at") else r.updated_at)
                               for r in recent)
                notices.append(Notice("program", f"program:{signature}", finished, "Программа завершена!",
                                      f"Все занятия программы «{plan.name}» выполнены. Как продолжим?", ("repeat_plan", "new_plan"), {"plan": signature}, 720))
    # Replace the nearest daily water slot, including after a retry or edit, but do not
    # drop all water reminders merely because a workout happened earlier that day.
    water = next((n for n in notices if n.kind == "water"), None)
    post_water = [n for n in notices if n.kind == "post_water"]
    if post_water:
        delivered = (await db.scalars(select(AICompanionReminder).where(AICompanionReminder.user_id == profile.user_id,
            AICompanionReminder.due_at >= start, AICompanionReminder.context["kind"].as_string() == "water"))).all()
        for n in post_water:
            if any((r.context or {}).get("delivered_ids") and abs(n.due - r.due_at) <= 60 * MINUTE for r in delivered):
                notices.remove(n)
            elif water and abs(n.due - water.due) <= 60 * MINUTE and water in notices:
                notices.remove(water)
    return {n.key: n for n in notices}


async def schedule(db, profile, now):
    live = await candidates(db, profile, now)
    if not live:
        return live
    existing = {r.dedupe_key: r for r in (await db.scalars(select(AICompanionReminder).where(
        AICompanionReminder.user_id == profile.user_id, AICompanionReminder.dedupe_key.in_(live)))).all()}
    for key, n in live.items():
        if n.due < profile.created_at or n.due + n.grace * MINUTE < now:
            continue
        row = existing.get(key)
        if row is None:
            kind = f"meal_{n.data['meal']}" if n.kind == "missing_meal" else "mobile"
            row = AICompanionReminder(user_id=profile.user_id, kind=kind, dedupe_key=key, due_at=n.due)
            db.add(row)
        elif row.status not in {"pending", "cancelled"} or (row.status == "cancelled" and row.attempts) or (row.context or {}).get("result"):
            continue
        row.status = "pending"
        row.due_at = n.due
        row.context = {**(row.context or {}), "mobile": True}
    return live


async def photo_ready(db, user_id, request_key, original_id=None, original_version=None, meal=None, meal_key=None):
    """Save the review reference in the outbox, never log the estimated meal here."""
    from src.database.models import User
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    profile = await service.profile_for(db, user_id)
    if not profile or not profile.enabled or not service.consent_is_current(await service.consent_for(db, user_id)):
        return
    settings = Settings.model_validate(profile.settings)
    if settings.notifications_paused or "photo" not in settings.mobile.topics:
        return
    key = "photo:" + sha256(request_key.encode()).hexdigest()
    await db.execute(insert(AICompanionReminder).values(user_id=user_id, kind="mobile", dedupe_key=key, due_at=service.now_utc(),
        context={"mobile": True, "photo_request": request_key, "original_id": original_id, "original_version": original_version,
                 "meal": meal, "meal_key": meal_key}).on_conflict_do_nothing(index_elements=["user_id", "dedupe_key"]))


async def current_notice(db, row, profile, now, live=None):
    context = row.context or {}
    if context.get("photo_request"):
        from .food import cached_food_estimate
        if "photo" not in Settings.model_validate(profile.settings).mobile.topics:
            return None
        result = await cached_food_estimate(db, row.user_id, context["photo_request"])
        entry = (result or {}).get("entry") or {}
        ids = entry.get("food_photo_attachment_ids") or []
        if not ids or entry.get("kind") != "meal":
            return None
        if context.get("original_id"):
            original = await db.get(AICompanionEntry, context["original_id"])
            if not original or original.user_id != row.user_id or original.version != context.get("original_version"):
                return None
        # Inspect recent saved photos, including older meals edited with this photo.
        records = (await db.scalars(select(AICompanionEntry.data).where(AICompanionEntry.user_id == row.user_id,
            AICompanionEntry.kind == "meal", AICompanionEntry.updated_at >= row.due_at - MINUTE))).all()
        if any(set(ids).intersection(r.get("food_photo_attachment_ids") or []) for r in records):
            return None
        return Notice("photo", row.dedupe_key, row.due_at, "Блюдо посчитано",
                      f"Примерно {entry['nutrition']['kcal']} ккал и {entry['nutrition']['protein']} г белка. Проверь порцию перед сохранением.",
                      ("review",), {"estimate": entry, "original_id": context.get("original_id"), "original_version": context.get("original_version"),
                                    "meal": context.get("meal"), "meal_key": context.get("meal_key"), "request": context["photo_request"]}, 120)
    if live is None:
        live = await candidates(db, profile, now)
    source = context.get("source")
    n = live.get(source or row.dedupe_key)
    if not n and source and source.startswith("bed:"):
        # A fixed fifteen-minute snooze can cross local midnight.
        original_day = date.fromisoformat(source.removeprefix("bed:"))
        zone = timezone_info(Settings.model_validate(profile.settings).timezone)
        if original_day == now.astimezone(zone).date() - timedelta(days=1):
            end_of_day = datetime.combine(original_day, time.max, zone)
            n = (await candidates(db, profile, end_of_day)).get(source)
    if n and context.get("source"):
        if n.kind == "training":
            n = replace(n, kind="training_later", title="Есть время на тренировку?", actions=("plan",))
        else:
            n = replace(n, actions=tuple(a for a in n.actions if a not in {"later", "bed_later"}))
        return replace(n, due=row.due_at)
    return n


async def deliver(db, row, profile, now, live=None):
    from src.app.services.push_notifications import _build_push_messages, _send_expo_push_messages, _delete_invalid_push_tokens
    context = row.context or {}
    if context.get("photo_seen") or context.get("result"):
        row.status = "sent" if context.get("delivered_ids") else "cancelled"
        return
    n = await current_notice(db, row, profile, now, live)
    if not n or now < n.due or now > n.due + n.grace * MINUTE:
        row.status = "cancelled"
        return
    if n.kind == "missing_meal":
        await save_reminder_message(db, row, n.title + " " + n.body)
    tokens = list((await db.scalars(select(UserPushToken).where(UserPushToken.user_id == row.user_id, UserPushToken.platform.in_(["ios", "android"])))).all())
    previous = (row.context or {}).get("delivered_ids", [])
    tokens = [t for t in tokens if t.id not in previous]
    data = {"type": "ai_companion", "mentor_notice": True, "key": row.dedupe_key, "kind": n.kind, "profile": profile.id}
    msgs = _build_push_messages(tokens, title=n.title, body=n.body, data=data)
    for message in msgs:
        if n.actions:
            message["categoryId"] = "mentor_" + "_".join(n.actions)
        message["ttl"] = max(1, int((n.due + n.grace * MINUTE - now).total_seconds()))
    row.attempts += 1
    if not msgs:
        row.status = "sent" if previous or row.message_id else "cancelled"
        return
    result = await _send_expo_push_messages(msgs)
    await _delete_invalid_push_tokens(db, push_tokens=tokens, invalid_tokens=set(result.invalid_tokens), commit=False)
    row.context = {**(row.context or {}), "delivered_ids": [*previous, *(t.id for t in tokens if t.expo_push_token in result.accepted_tokens)],
                   "offered": list(n.actions), "kind": n.kind, "plan": n.data.get("plan"), "offered_ml": n.data.get("ml")}
    if result.failed_tokens - result.invalid_tokens:
        row.status = "pending" if row.attempts < 5 else "failed"
        row.next_attempt_at = now + min(8, 2 ** row.attempts) * MINUTE
    else:
        row.status = "sent" if row.context["delivered_ids"] or row.message_id else "cancelled"
