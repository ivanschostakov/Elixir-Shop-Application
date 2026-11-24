"""Resolve native actions against live, owned records; serialize replies with diary changes."""
from datetime import date, datetime, timedelta
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import select
from src.database.models import User
from src.database.models.ai.companion import AICompanionEntry, AICompanionReminder

from . import service
from .meals import meal_type
from .mobile_push import current_notice
from .push_rules import MINUTE, Notice, plan_signature
from .schemas import Action, EntryData, Settings, WorkoutData, WorkoutMove, WorkoutPlan
from .timezones import timezone_info


def expired():
    return HTTPException(409, "Это напоминание больше не актуально.")


async def local_session(db, profile, key, now):
    try:
        mode, entry_id, stamp = key.split(":")
        record = await db.get(AICompanionEntry, int(entry_id))
    except (ValueError, OverflowError):
        raise expired()
    if not record or record.user_id != profile.user_id or record.kind != "workout":
        raise expired()
    w = record.data["workout"]
    opts = Settings.model_validate(profile.settings).mobile
    if w["status"] != "in_progress":
        raise expired()
    if mode == "rest" and "rest" in opts.topics and w.get("rest_ends_at") and not w.get("paused_at"):
        end = datetime.fromisoformat(w["rest_ends_at"])
        if str(round(end.timestamp()*1000)) == stamp and end - timedelta(seconds=2) <= now <= end + 30 * MINUTE:
            return Notice("rest", key, end, "Отдых закончился", w["name"], ("continue", "extend"), {"entry_id": record.id})
    if mode == "empty" and "unfinished" in opts.topics and str(record.version) == stamp and not any(s["completed"] for e in w["exercises"] for s in e["sets"]):
        return Notice("empty", key, now, "Начнём тренировку?", "Она открыта, подходов пока нет.", ("restart", "close_empty"), {"entry_id": record.id})
    raise expired()


async def resolve(db, user_id, profile_id, key, action=None, minutes=30, ml=None, score=None, start_workout=False, duration_minutes=None):
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    profile = await service.profile_for(db, user_id)
    if not profile or not profile.enabled or profile.id != profile_id:
        raise HTTPException(404, "Напоминание не найдено")
    await service.require_consent(db, user_id)
    now = service.now_utc()
    row = await db.scalar(select(AICompanionReminder).where(AICompanionReminder.user_id == user_id, AICompanionReminder.dedupe_key == key))
    context = (row.context or {}) if row else {}
    if "result" in context:
        return context["result"]
    if key.startswith(("rest:", "empty:")):
        notice = await local_session(db, profile, key, now)
        if action and row is None:
            row = AICompanionReminder(user_id=user_id, kind="mobile_local", dedupe_key=key, due_at=now, status="sent")
            db.add(row)
            await db.flush()
    else:
        if not row or not context.get("mobile") or row.status not in {"sent", "pending", "failed"} or not context.get("delivered_ids"):
            raise expired()
        notice = await current_notice(db, row, profile, now)
        if not notice or now < row.due_at or now > row.due_at + timedelta(hours=12):
            raise expired()
    if context.get("plan") and context["plan"] != notice.data.get("plan"):
        raise expired()
    if context.get("kind") and context["kind"] != notice.kind:
        raise expired()
    if action is None:
        result = notice.content()
        # Only the authenticated review screen receives health data; lock-screen payloads contain IDs.
        result["actions"] = [a for a in notice.actions if a in context.get("offered", notice.actions)]
        return result
    if action not in notice.actions or action not in context.get("offered", notice.actions):
        raise expired()
    result = await respond(db, profile, row, notice, action, minutes, ml, score, start_workout, duration_minutes, now)
    # Navigation remains repeatable. A mutation from a second device returns the original receipt.
    if result.pop("mutated", False):
        row.context = {**context, "result": result, "answered": action}
    await db.flush()
    return result


async def respond(db, profile, row, n, action, minutes, ml, score, start_workout, duration_minutes, now):
    uid = profile.user_id
    settings = Settings.model_validate(profile.settings)
    zone = timezone_info(settings.timezone)
    day = now.astimezone(zone).date()
    data = n.data
    receipt = {"mutated": True, "screen": "done", "message": "Готово"}
    record = await db.get(AICompanionEntry, data["entry_id"]) if data.get("entry_id") else None
    if record and record.user_id != uid:
        raise expired()

    async def save(kind, suffix="", **kwargs):
        key = sha256(f"mobile:{row.id}:{action}:{suffix}".encode()).hexdigest()
        await service.apply_action(db, uid, Action(request_key=key, kind=kind, **kwargs))

    if action in {"later", "bed_later"}:
        delay = 15 if action == "bed_later" else minutes
        due = now + delay * MINUTE
        if action != "bed_later" and due.astimezone(zone).date() != day:
            raise HTTPException(422, "Выберите время до конца сегодняшнего дня")
        db.add(AICompanionReminder(user_id=uid, kind="mobile", dedupe_key=f"later:{row.id}", due_at=due,
                                   context={"mobile": True, "source": row.dedupe_key}))
        return {**receipt, "message": f"Напоминание в {due.astimezone(zone):%H:%M}"}
    if action == "dismiss":
        return receipt
    if action in {"water", "water250", "water500", "other_water"}:
        # Use the quantity actually offered on the lock screen. A changed portion must be reviewed.
        offered = (row.context or {}).get("offered_ml")
        if action == "water" and offered and data["ml"] != offered:
            raise expired()
        if action == "other_water" and ml is None:
            return {"screen": "water_amount"}
        amount = {"water": data.get("ml"), "water250": 250, "water500": 500, "other_water": ml}[action]
        await save("entry", entry=EntryData(kind="water", occurred_at=now, water_ml=amount))
        return {**receipt, "message": f"Записано {amount} мл воды"}
    if action == "log_meal":
        return {"screen": "meal", "meal": data["meal"]}
    if action == "repeat_meal":
        start = datetime.combine(day-timedelta(days=1), datetime.min.time(), zone)
        meals = [r for r in await service.entries_for(db, uid, start, start+timedelta(days=1), "meal", limit=10001) if meal_type(r, zone) == data["meal"]]
        if not meals:
            raise expired()
        for r in meals:
            entry = EntryData.model_validate({**r.data, "occurred_at": now, "meal_type": data["meal"], "water_ml": None,
                                              "food_photo_attachment_ids": [], "favorite": False})
            await save("entry", str(r.id), entry=entry)
        return {**receipt, "message": "Приём пищи записан"}
    if action == "suggest":
        history = await service.entries_for(db, uid, now-timedelta(days=28), now, "meal", limit=10000)
        gaps = data["gaps"]
        def difference(r):
            nutrients = r.data["nutrition"]
            targets = profile.data["nutrition"]
            return sum(abs(float(nutrients[k]) - gaps.get(k, 0)) / max(1, float(targets.get(k) or 0)) for k in targets)
        choices = [r for r in history if any(float(r.data["nutrition"][k]) > 0 for k in gaps)]
        closest = min(choices, key=difference) if choices else None
        return {"screen": "suggestion", "meal": data["meal"], "gaps": gaps, "water_gap": data.get("water_gap", 0),
                "dish": service.dump(closest) if closest else None}
    if action == "review":
        original = await db.get(AICompanionEntry, data["original_id"]) if data.get("original_id") else None
        return {"screen": "photo", "estimate": data["estimate"], "original": service.dump(original), "meal": data["meal"],
                "meal_key": data["meal_key"], "request": data["request"]}
    if action in {"checkin", "rested", "partly", "poorly"}:
        if action == "checkin" and score is None:
            return {"screen": "rating", "title": "Как самочувствие сегодня?", "body": "От 1 — очень плохо до 5 — отлично"}
        values = {"wellbeing": score} if action == "checkin" else {"sleep_quality": {"rested": 3, "partly": 2, "poorly": 1}[action]}
        midnight = datetime.combine(day, datetime.min.time(), zone)
        daily = select(AICompanionEntry).where(AICompanionEntry.user_id == uid, AICompanionEntry.kind == "wellbeing",
            AICompanionEntry.occurred_at.between(midnight, now)).order_by(AICompanionEntry.occurred_at.desc(), AICompanionEntry.id.desc()).limit(1)
        latest = await db.scalar(daily)
        if latest:
            await save("entry", resource_id=latest.id, expected_version=latest.version, entry=EntryData.model_validate({**latest.data, **values}))
        else:
            await save("entry", entry=EntryData(kind="wellbeing", occurred_at=now, **values))
            latest = await db.scalar(daily)
        return {**receipt, "message": "Самочувствие записано" if action == "checkin" else "Качество сна записано", "wellbeing_id": latest.id}
    if action in {"calmer", "same", "tenser"}:
        entry = EntryData.model_validate({**record.data, "stress_change": action})
        await save("entry", resource_id=record.id, expected_version=record.version, entry=entry)
        return {**receipt, "message": "Ответ сохранён рядом с отметкой о стрессе"}
    if action in {"continue", "restart", "close_empty", "finish", "extend", "easy", "right", "hard"}:
        w = dict(record.data["workout"])
        if action == "continue":
            return {"screen": "session", "entry_id": record.id}
        if action == "close_empty":
            await save("delete_entry", resource_id=record.id, expected_version=record.version)
            return {**receipt, "message": "Пустая тренировка закрыта"}
        if action == "restart":
            w.update(reported_duration_seconds=None, timer_started_at=now.isoformat(), duration_seconds=0, rest_ends_at=None, paused_at=None, current_exercise_index=0)
        elif action == "finish":
            # Finishing long after the notification must not count idle hours as exercise.
            w.update(status="completed", rest_ends_at=None, paused_at=None)
        elif action == "extend":
            w["rest_ends_at"] = (now+timedelta(seconds=30)).isoformat()
        else:
            w["effort"] = action
        await save("entry", resource_id=record.id, expected_version=record.version, entry=EntryData.model_validate({**record.data, "workout": w}))
        if action in {"restart", "extend"}:
            return {**receipt, "screen": "session", "entry_id": record.id}
        return {**receipt, "message": "Тренировка завершена" if action == "finish" else "Оценка нагрузки сохранена"}
    plan = WorkoutPlan.model_validate(profile.data["workout_plan"])
    if data.get("plan") != plan_signature(plan):
        raise expired()
    if action == "new_plan":
        return {"screen": "new_plan"}
    if action == "repeat_plan":
        start = day + timedelta(days=(plan.start_date.weekday()-day.weekday()-1) % 7 + 1)
        plan.end_date = start + (plan.end_date - plan.start_date)
        plan.start_date = start
        plan.moves = []
        await save("workout_plan", expected_version=profile.version, workout_plan=plan)
        return {**receipt, "message": f"Программа начнётся {start:%d.%m}"}
    block = next(b for b in plan.scheduled(day) if b.key == data["block"])
    if action == "move":
        tomorrow = day + timedelta(days=1)
        if plan.scheduled(tomorrow) or (plan.end_date and tomorrow > plan.end_date):
            raise expired()
        # Preserve the original occurrence when moving a previously moved session again.
        prior = next((m for m in plan.moves if m.day_key == block.key and m.destination == day), None)
        if prior:
            prior.destination = tomorrow
        else:
            plan.moves.append(WorkoutMove(original=day, destination=tomorrow, day_key=block.key))
        await save("workout_plan", expected_version=profile.version, workout_plan=plan)
        return {**receipt, "message": f"Тренировка перенесена на {tomorrow:%d.%m}"}
    if action in {"plan", "log_workout"} and not start_workout:
        return {"screen": "plan", "block": block.model_dump(mode="json"), "date": day.isoformat(), "retrospective": action == "log_workout"}
    if action in {"short", "plan", "log_workout"}:
        retrospective = action == "log_workout"
        if retrospective and not duration_minutes:
            raise HTTPException(422, "Укажите длительность тренировки")
        short = action == "short"
        selected = block.exercises[:(len(block.exercises) + 1) // 2] if short else block.exercises
        exercises = []
        for exercise in selected:
            count = min(2, exercise.sets) if short else exercise.sets
            exercises.append({**exercise.model_dump(exclude={"sets"}), "sets": [{} for _ in range(count)], "target_sets": count})
        w = WorkoutData(name=block.name[:189] + " · короткая" if short else block.name, plan_day_key=block.key, scheduled_date=day,
                        exercises=exercises, timer_started_at=None if retrospective else now,
                        reported_duration_seconds=duration_minutes * 60 if retrospective else None)
        await save("entry", entry=EntryData(kind="workout", occurred_at=now, workout=w))
        new_id = await db.scalar(select(AICompanionEntry.id).where(AICompanionEntry.user_id == uid, AICompanionEntry.kind == "workout",
            AICompanionEntry.occurred_at == now, AICompanionEntry.data["workout"]["plan_day_key"].as_string() == block.key))
        return {**receipt, "screen": "session", "entry_id": new_id}
    raise expired()
