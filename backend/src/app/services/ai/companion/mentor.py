"""Read models calculated from confirmed records, never model drafts or targets."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from pydantic import Field
from sqlalchemy import select

from src.database.models.ai.companion import AICompanionEntry, AICompanionEvent
from .schemas import EntryData, MeasurementData, Nutrition, ProfileData, Settings, StrictModel, WorkoutPlan
from .timezones import timezone_info


class CourseCounts(StrictModel):
    scheduled: int = 0
    done: int = 0
    skipped: int = 0
    pending: int = 0


class WorkoutTotals(StrictModel):
    sessions: int = 0
    completed: int = 0
    in_progress: int = 0
    completed_sets: int = 0
    reps: int = 0
    volume_kg: Decimal = Decimal(0)
    duration_seconds: int = 0


class MeasurementTotals(StrictModel):
    count: int = 0
    latest: dict[str, Decimal | None] = Field(default_factory=dict)
    change: dict[str, Decimal | None] = Field(default_factory=dict)


class WellbeingTotals(StrictModel):
    entries: int = 0
    average_score: Decimal | None = None
    energy_measurements: int = 0
    average_energy: Decimal | None = None


class NutritionTotals(StrictModel):
    # Period totals can legitimately exceed the per-meal/profile input limits.
    kcal: Decimal = Field(ge=0)
    protein: Decimal = Field(ge=0)
    fat: Decimal = Field(ge=0)
    carbs: Decimal = Field(ge=0)


class ProgressSummary(StrictModel):
    from_at: str = Field(alias="from")
    to: str
    nutrition: NutritionTotals
    meals_logged: int
    days_with_meals: int
    weight_measurements: int
    weight_change_kg: Decimal | None
    events: dict[Literal["done", "skipped", "pending"], int]
    coverage_note: str
    workouts: WorkoutTotals
    measurements: MeasurementTotals
    wellbeing: WellbeingTotals


class MentorTask(StrictModel):
    id: str
    kind: Literal["course", "workout"]
    label: str
    status: Literal["pending", "done", "skipped", "in_progress"]
    resource_id: int | None = None
    version: int | None = None
    scheduled_at: datetime | None = None
    plan_day_key: str | None = None


class TodayWorkouts(StrictModel):
    scheduled: int = 0
    completed: int = 0
    in_progress: int = 0


class TodayNutrition(StrictModel):
    consumed: NutritionTotals
    target: Nutrition | None = None
    remaining: Nutrition | None = None


class MentorToday(StrictModel):
    date: date
    course: CourseCounts
    workouts: TodayWorkouts
    tasks: list[MentorTask]
    nutrition: TodayNutrition


class MentorWeek(StrictModel):
    from_date: date
    to_date: date
    summary: ProgressSummary


class DiaryEntryRead(StrictModel):
    id: int
    user_id: int
    kind: str
    occurred_at: datetime
    data: EntryData
    source: str
    source_message_id: int | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class FavoriteMealsRead(StrictModel):
    entries: list[DiaryEntryRead]
    limit: int = 200
    may_have_more: bool = False


class MentorDashboard(StrictModel):
    workout_plan: WorkoutPlan | None = None
    latest_weight: DiaryEntryRead | None = None
    today: MentorToday
    week: MentorWeek


def progress_totals(entries):
    workouts = WorkoutTotals()
    measurements = []
    scores = []
    energy = []
    wellbeing_count = 0
    for entry in entries:
        if entry.kind == "workout":
            workout = EntryData.model_validate(entry.data).workout
            workouts.sessions += 1
            workouts.completed += workout.status == "completed"
            workouts.in_progress += workout.status == "in_progress"
            workouts.duration_seconds += workout.duration_seconds
            for exercise in workout.exercises:
                for item in exercise.sets:
                    if item.completed:
                        workouts.completed_sets += 1
                        workouts.reps += item.reps
                        workouts.volume_kg += item.weight_kg * item.reps
        elif entry.kind == "measurement":
            measurements.append(entry)
        elif entry.kind == "wellbeing":
            wellbeing_count += 1
            if entry.data.get("wellbeing") is not None:
                scores.append(Decimal(str(entry.data["wellbeing"])))
            if entry.data.get("energy") is not None:
                energy.append(Decimal(str(entry.data["energy"])))
    measurements.sort(key=lambda e: (e.occurred_at, e.id))
    measurement_totals = MeasurementTotals(count=len(measurements))
    for name in MeasurementData.model_fields:
        values = [Decimal(str(entry.data["measurement"][name])) for entry in measurements if entry.data["measurement"].get(name) is not None]
        measurement_totals.latest[name] = values[-1] if values else None
        measurement_totals.change[name] = values[-1] - values[0] if len(values) > 1 else None
    return {
        "workouts": workouts.model_dump(mode="json"),
        "measurements": measurement_totals.model_dump(mode="json"),
        "wellbeing": WellbeingTotals(entries=wellbeing_count, average_score=sum(scores) / len(scores) if scores else None,
            energy_measurements=len(energy), average_energy=sum(energy) / len(energy) if energy else None).model_dump(mode="json"),
    }


def remaining_nutrition(consumed, target):
    if target is None:
        return None
    return Nutrition(**{name: max(Decimal(0), getattr(target, name) - Decimal(str(consumed[name]))) for name in Nutrition.model_fields})


async def dashboard(db, user_id):
    from . import service
    profile = await service.profile_for(db, user_id)
    if not profile or not profile.enabled or not service.consent_is_current(await service.consent_for(db, user_id)):
        return None
    data = ProfileData.model_validate(profile.data)
    zone = timezone_info(Settings.model_validate(profile.settings).timezone)
    now = service.now_utc()
    midnight = now.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    today = midnight.date()
    start, end = midnight.astimezone(timezone.utc), (midnight + timedelta(days=1)).astimezone(timezone.utc)
    week_start = midnight - timedelta(days=midnight.weekday())
    today_summary = await service.summary_for(db, user_id, start, end)
    week_summary = await service.summary_for(db, user_id, week_start.astimezone(timezone.utc), (week_start + timedelta(days=7)).astimezone(timezone.utc))
    events = list((await db.execute(select(AICompanionEvent).where(
        AICompanionEvent.user_id == user_id, AICompanionEvent.scheduled_at >= start,
        AICompanionEvent.scheduled_at < end, AICompanionEvent.status != "cancelled",
    ).order_by(AICompanionEvent.scheduled_at, AICompanionEvent.id))).scalars())
    tasks = [MentorTask(id=f"course:{event.id}", kind="course", label=event.data["name"], status=event.status,
        resource_id=event.id, version=event.version, scheduled_at=event.scheduled_at) for event in events]
    workouts = await service.entries_for(db, user_id, start, min(end, now + timedelta(microseconds=1)), "workout", limit=10001)
    # Scheduling is local-date based; actual sessions retain their own date and
    # exercise snapshot even when the weekly plan is subsequently edited.
    scheduled = []
    plan = data.workout_plan
    if plan and plan.start_date <= today and (plan.end_date is None or today <= plan.end_date):
        scheduled = [day for day in plan.days if today.weekday() in day.weekdays]
    linked = set()
    for day in scheduled:
        matches = [e for e in workouts if e.data["workout"].get("plan_day_key") == day.key and e.data["workout"].get("scheduled_date") == today.isoformat()]
        entry = matches[0] if matches else None
        if entry:
            linked.add(entry.id)
        tasks.append(MentorTask(id=f"workout:{today}:{day.key}", kind="workout", label=day.name,
            status=("done" if entry.data["workout"]["status"] == "completed" else "in_progress") if entry else "pending",
            resource_id=entry.id if entry else None, version=entry.version if entry else None, plan_day_key=day.key))
    for entry in workouts:
        if entry.id not in linked:
            tasks.append(MentorTask(id=f"workout:{entry.id}", kind="workout", label=entry.data["workout"]["name"],
                status="done" if entry.data["workout"]["status"] == "completed" else "in_progress",
                resource_id=entry.id, version=entry.version, plan_day_key=entry.data["workout"].get("plan_day_key")))
    latest = await service.latest_weight(db, user_id, now)
    return MentorDashboard(
        workout_plan=plan, latest_weight=service.dump(latest),
        today=MentorToday(date=today, tasks=tasks,
            course=CourseCounts(scheduled=len(events), **today_summary["events"]),
            workouts=TodayWorkouts(scheduled=len(scheduled), completed=today_summary["workouts"]["completed"], in_progress=today_summary["workouts"]["in_progress"]),
            nutrition=TodayNutrition(consumed=today_summary["nutrition"], target=data.nutrition, remaining=remaining_nutrition(today_summary["nutrition"], data.nutrition))),
        week=MentorWeek(from_date=week_start.date(), to_date=(week_start + timedelta(days=7)).date(), summary=week_summary),
    ).model_dump(mode="json", by_alias=True)
