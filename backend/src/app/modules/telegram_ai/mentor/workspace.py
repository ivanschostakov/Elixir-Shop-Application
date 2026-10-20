from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.database.models import TelegramAIJournal
from src.app.modules.telegram_ai.profile import Identity
from src.app.modules.telegram_ai.journal import dump, now, settings_for
from .common import SECTIONS, router
from .helpers import require_section, section_enabled
from .schemas import MODELS, Report
from .food import remaining


def summarize(rows, instant, zone, days=7):
    local = instant.astimezone(zone)
    start = datetime.combine(local.date()-timedelta(days=days-1), time.min, zone)
    week = [r for r in rows if start <= r.occurred_at <= instant]
    confirmed = [r for r in week if r.status == "confirmed"]
    workouts = [r for r in confirmed if r.kind == "workout"]
    activities = [r for r in confirmed if r.kind == "activity_log"]
    weights = sorted([r for r in confirmed if r.kind == "weight"], key=lambda r: (r.occurred_at, r.id))
    events = [r for r in week if r.kind == "course_event" and r.status != "cancelled"]
    seven_start = datetime.combine(local.date()-timedelta(days=6), time.min, zone)
    seven_weights = [r.data["weight_kg"] for r in weights if r.occurred_at >= seven_start]
    wellbeing = [r.data["score"] for r in confirmed if r.kind == "wellbeing"]
    energy = [r.data["energy_score"] for r in confirmed if r.kind == "wellbeing" and r.data.get("energy_score") is not None]
    daily = {}
    for row in confirmed:
        if row.kind == "meal":
            day = row.occurred_at.astimezone(zone).date()
            value = daily.setdefault(day, {"kcal": 0, "protein": 0})
            for key in value: value[key] += row.data.get(key, 0)
    targets = sorted([r for r in rows if r.kind == "target" and r.status in {"confirmed", "replaced"}], key=lambda r: (r.occurred_at, r.id))
    protein_actual = protein_target = 0
    protein_days = 0
    for day, values in daily.items():
        target = next((r for r in reversed(targets) if r.occurred_at.astimezone(zone).date() <= day), None)
        if target and target.data.get("protein") and target.data.get("source") in {"user", "specialist"}:
            protein_actual += values["protein"]
            protein_target += target.data["protein"]
            protein_days += 1
    programs = sorted([r for r in rows if r.kind == "program" and r.status in {"confirmed", "replaced"}], key=lambda r: (r.occurred_at, r.id))
    planned = 0
    completed_planned_days = set()
    for n in range(days):
        day = start.date()+timedelta(days=n)
        program = next((r for r in reversed(programs) if r.occurred_at.astimezone(zone).date() <= day), None)
        if program and any(e["weekday"] == day.weekday() for e in program.data["exercises"]):
            planned += 1
            names = {e["name"].casefold() for e in program.data["exercises"] if e["weekday"] == day.weekday()}
            if any(r.occurred_at.astimezone(zone).date() == day and any(s["exercise"].casefold() in names for s in r.data["sets"]) for r in workouts): completed_planned_days.add(day)
    return {"days": days, "from": start.date().isoformat(), "to": local.date().isoformat(),
        "nutrition_days": len(daily), "average_kcal": round(sum(v["kcal"] for v in daily.values())/len(daily), 1) if daily else None,
        "protein_target_percent": round(100*protein_actual/protein_target, 1) if protein_target else None,
        "protein_target_days": protein_days, "planned_workouts": planned,
        "planned_workouts_done": len(completed_planned_days),
        "weight_measurements": len(weights), "weight_mean_7d": round(sum(seven_weights)/len(seven_weights), 2) if seven_weights else None,
        "weight_mean": round(sum(r.data["weight_kg"] for r in weights)/len(weights), 2) if weights else None,
        "weight_samples": len(weights),
        "weight_samples_7d": len(seven_weights), "wellbeing_mean": round(sum(wellbeing)/len(wellbeing), 2) if wellbeing else None,
        "wellbeing_samples": len(wellbeing), "energy_mean": round(sum(energy)/len(energy), 2) if energy else None,
        "energy_samples": len(energy), "meals": sum(r.kind == "meal" for r in confirmed),
        "workouts": len(workouts), "duration_minutes": round(sum(r.data["duration_minutes"] for r in workouts), 1),
        "activities": len(activities), "activity_duration_minutes": round(sum(r.data["duration_minutes"] for r in activities), 1),
        "volume_kg": round(sum(s["weight_kg"]*s["reps"] for r in workouts for s in r.data["sets"]), 1),
        "weight_change_kg": round(weights[-1].data["weight_kg"]-weights[0].data["weight_kg"], 2) if len(weights)>1 else None,
        "course_due": len(events), "course_done": sum(r.status == "done" for r in events),
        "nutrition": {k: round(sum(r.data.get(k, 0) for r in confirmed if r.kind == "meal"), 1)
                      for k in ("kcal", "protein", "fat", "carbs")}}


@router.post("/report")
async def report(payload: Report, db: AsyncSession = Depends(get_db)):
    require_section("progress")
    settings = await settings_for(db, payload.telegram_user_id)
    instant = now()
    zone = ZoneInfo(settings["timezone"])
    start = datetime.combine(instant.astimezone(zone).date()-timedelta(days=payload.days-1), time.min, zone)
    rows = list((await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.kind.in_(["weight", "workout", "activity_log", "meal", "course_event", "wellbeing", "target", "program"]), (TelegramAIJournal.occurred_at >= start) | TelegramAIJournal.kind.in_(["target", "program"]), TelegramAIJournal.occurred_at <= instant).order_by(TelegramAIJournal.occurred_at, TelegramAIJournal.id))).scalars())
    return summarize(rows, instant, zone, payload.days)


async def workspace_state(db, uid, totals=None):
    settings = await settings_for(db, uid)
    instant = now()
    zone = ZoneInfo(settings["timezone"])
    # Query an explicit date window, never silently truncate weekly totals.
    rows = list((await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == uid, TelegramAIJournal.kind.in_([*MODELS, "meal", "weight", "course_event"]), TelegramAIJournal.status.not_in(["draft", "cancelled"]), (TelegramAIJournal.status != "replaced") | TelegramAIJournal.kind.in_(["target", "program"]), (TelegramAIJournal.occurred_at >= instant-timedelta(days=31)) | TelegramAIJournal.kind.in_(["target", "program", "course"])).order_by(TelegramAIJournal.occurred_at, TelegramAIJournal.id))).scalars())
    current = lambda kind: next((r for r in reversed(rows) if r.kind == kind and r.status == "confirmed"), None)
    target = current("target")
    program = current("program")
    today = [r for r in rows if r.occurred_at.astimezone(zone).date() == instant.astimezone(zone).date()]
    courses = []
    for course in (r for r in rows if r.kind == "course" and r.status == "confirmed"):
        events = list((await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == uid, TelegramAIJournal.kind == "course_event", TelegramAIJournal.data["course_id"].as_integer() == course.id).order_by(TelegramAIJournal.occurred_at))).scalars())
        done = sum(e.status == "done" for e in events)
        due_count = sum(e.occurred_at <= instant and e.status != "cancelled" for e in events)
        pending = [e for e in events if e.status == "pending" and e.occurred_at >= instant]
        supply = None
        if course.data.get("amount_per_intake") is not None and course.data.get("supply_amount") is not None:
            from src.app.modules.telegram_ai.course_inventory import calculate_supply
            try: supply = calculate_supply(course, events, instant)
            except ValueError:
                supply = {"available": False, "remaining": None, "unit": "", "intakes_available": 0,
                    "runs_out_at": None, "reason": "Запас и расход сохранены неоднозначно. Уточните фактический остаток и расход по вашей схеме."}
        courses.append({**dump(course), "done": done, "due": due_count, "supply": supply, "next_event": dump(pending[0]) if pending else None, "calendar": [dump(e) for e in events if e.occurred_at >= instant-timedelta(days=7)][:40]})
    statuses = list((await db.execute(select(TelegramAIJournal.id, TelegramAIJournal.kind, TelegramAIJournal.status).where(TelegramAIJournal.telegram_user_id == uid, TelegramAIJournal.kind.in_([*MODELS, "meal"])).order_by(TelegramAIJournal.id.desc()).limit(20))).mappings())
    return {"sections": {s: section_enabled(s) for s in sorted(SECTIONS)},
        "record_statuses": [dict(row) for row in statuses],
        "target": dump(target) if target else None, "remaining": remaining(target.data if target else None, totals or {}),
        "program": dump(program) if program else None,
        "today_exercises": [e for e in program.data["exercises"] if e["weekday"] == instant.astimezone(zone).weekday()] if program else [],
        "today_course": [dump(r) for r in today if r.kind == "course_event" and r.status != "cancelled"],
        "today_workouts": [dump(r) for r in today if r.kind == "workout" and r.status == "confirmed"],
        "today_activities": [dump(r) for r in today if r.kind == "activity_log" and r.status == "confirmed"],
        "recent_workouts": [dump(r) for r in rows if r.kind == "workout" and r.status == "confirmed"][-10:],
        "recent_activities": [dump(r) for r in rows if r.kind == "activity_log" and r.status == "confirmed"][-10:],
        "active_workout": next((dump(r) for r in reversed(rows) if r.kind == "workout" and r.status == "active"), None),
        "today_wellbeing": [dump(r) for r in today if r.kind == "wellbeing" and r.status == "confirmed"],
        "courses": courses, "weekly": summarize(rows, instant, zone),
        "measurements": [dump(r) for r in rows if r.kind == "measurement" and r.status == "confirmed"][-30:]}


@router.post("/state")
async def state(payload: Identity, db: AsyncSession = Depends(get_db)):
    return await workspace_state(db, payload.telegram_user_id)
