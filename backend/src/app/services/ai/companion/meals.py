"""Meal grouping, drink-water totals and local-time eating habits."""
from collections import Counter
from datetime import time, timedelta

from fastapi import HTTPException
from sqlalchemy import select

from src.database.models.ai.companion import AICompanionEntry
from .schemas import Settings
from .timezones import timezone_info

MEAL_TYPES = ("breakfast", "lunch", "dinner")


def meal_type(entry, zone):
    saved = entry.data.get("meal_type")
    if saved in (*MEAL_TYPES, "extra"):
        return saved
    hour = entry.occurred_at.astimezone(zone).hour
    return "breakfast" if hour < 11 else "lunch" if hour < 17 else "dinner"


def water_target(profile):
    settings = Settings.model_validate(profile.settings)
    # EFSA 2010 total-water reference, with 80% allocated to drinks.
    # Starting tracking goal, editable independently of calories.
    return settings.water_goal_ml or (1600 if profile.data.get("sex") == "female" else 2000)


def eating_habits(entries, zone, today):
    result = {}
    for kind in MEAL_TYPES:
        days = {}
        for entry in sorted(entries, key=lambda row: (row.occurred_at, row.id)):
            local = entry.occurred_at.astimezone(zone)
            if local.date() >= today or meal_type(entry, zone) != kind:
                continue
            # Several dishes in one meal must not outweigh other days.
            days.setdefault(local.date(), (local.hour * 60 + local.minute) // 30)
        if len(days) < 3:
            result[kind] = {"time": None, "days": len(days)}
            continue
        counts = Counter(days.values())
        recent = {bucket: max(day for day, value in days.items() if value == bucket) for bucket in counts}
        bucket = max(counts, key=lambda value: (counts[value], recent[value]))
        result[kind] = {"time": f"{bucket // 2:02}:{(bucket % 2) * 30:02}", "days": len(days)}
    return result


async def history_and_habits(db, user_id, settings, now):
    zone = timezone_info(settings.timezone)
    rows = list((await db.execute(select(AICompanionEntry).where(
        AICompanionEntry.user_id == user_id, AICompanionEntry.kind == "meal",
        AICompanionEntry.occurred_at >= now - timedelta(days=28), AICompanionEntry.occurred_at <= now,
    ).order_by(AICompanionEntry.occurred_at.desc(), AICompanionEntry.id.desc()).limit(10000))).scalars())
    return rows, eating_habits(rows, zone, now.astimezone(zone).date())


def missing_meal_due_at(entries, habits, zone, today):
    from .jobs import local_due
    logged = {meal_type(entry, zone) for entry in entries if entry.occurred_at.astimezone(zone).date() == today}
    deadlines = []
    for kind in MEAL_TYPES:
        slot = habits[kind]["time"]
        if slot and kind not in logged:
            start = local_due(today, time.fromisoformat(slot), zone)
            if start is not None:
                deadlines.append(start + timedelta(minutes=30))
    return min(deadlines, default=None)


async def library(db, user_id):
    from . import service
    from .photos import serialize_entries
    profile = await service.profile_for(db, user_id)
    if profile is None or not profile.enabled:
        raise HTTPException(403, "Сопровождение отключено")
    await service.require_consent(db, user_id)
    rows, habits = await history_and_habits(db, user_id, Settings.model_validate(profile.settings), service.now_utc())
    recent, seen = [], set()
    for row in rows:
        key = (row.data.get("note") or row.data.get("name") or "").strip().casefold()
        if key and key not in seen:
            recent.append(row)
            seen.add(key)
        if len(recent) == 20:
            break
    return {"entries": await serialize_entries(db, user_id, recent), "habits": habits}
