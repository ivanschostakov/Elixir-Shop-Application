from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .timezones import normalize_timezone


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Nutrition(StrictModel):
    kcal: Decimal = Field(ge=0, le=100000)
    protein: Decimal = Field(ge=0, le=10000)
    fat: Decimal = Field(ge=0, le=10000)
    carbs: Decimal = Field(ge=0, le=10000)


class WorkoutExercisePlan(StrictModel):
    key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    sets: int = Field(ge=1, le=30)
    target_reps: int | None = Field(default=None, ge=1, le=1000)
    target_reps_max: int | None = Field(default=None, ge=1, le=1000)
    target_weight_kg: Decimal | None = Field(default=None, ge=0, le=1000)
    rest_seconds: int | None = Field(default=None, ge=0, le=1800)

    @model_validator(mode="after")
    def valid_rep_range(self):
        if self.target_reps_max is not None and (self.target_reps is None or self.target_reps_max < self.target_reps):
            raise ValueError("The upper rep target requires a lower target and cannot be smaller")
        return self


class WorkoutDay(StrictModel):
    key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    weekdays: list[int] = Field(min_length=1, max_length=7)
    exercises: list[WorkoutExercisePlan] = Field(min_length=1, max_length=30)
    duration_minutes: int | None = Field(default=None, ge=1, le=300)

    @model_validator(mode="after")
    def unique_schedule(self):
        if len(set(self.weekdays)) != len(self.weekdays) or any(day not in range(7) for day in self.weekdays):
            raise ValueError("Weekdays must be unique integers from 0 to 6")
        if len({exercise.key for exercise in self.exercises}) != len(self.exercises):
            raise ValueError("Exercise keys must be unique")
        return self


class WorkoutMove(StrictModel):
    day_key: str = Field(min_length=1, max_length=80)
    original: date
    destination: date


class WorkoutPlan(StrictModel):
    moves: list[WorkoutMove] = Field(default_factory=list, max_length=730)

    def scheduled(self, day: date):
        if day < self.start_date or (self.end_date and day > self.end_date):
            return []
        removed = {m.day_key for m in self.moves if m.original == day}
        added = {m.day_key for m in self.moves if m.destination == day}
        return [d for d in self.days if d.key in added or (d.key not in removed and day.weekday() in d.weekdays)]

    name: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date | None = None
    days: list[WorkoutDay] = Field(min_length=1, max_length=14)

    @model_validator(mode="after")
    def valid_plan(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("Workout plan ends before it starts")
        if len({day.key for day in self.days}) != len(self.days):
            raise ValueError("Workout day keys must be unique")
        days = {day.key: day for day in self.days}
        removed = {(move.original, move.day_key) for move in self.moves}
        if len(removed) != len(self.moves) or len({move.destination for move in self.moves}) != len(self.moves):
            raise ValueError("A workout occurrence can only be moved once to a free date")
        for move in self.moves:
            original = days.get(move.day_key)
            if (not original or move.original.weekday() not in original.weekdays or
                    not self.start_date <= move.original < move.destination or (self.end_date and move.destination > self.end_date)):
                raise ValueError("Invalid workout occurrence or destination")
            if any(move.destination.weekday() in d.weekdays and (move.destination, d.key) not in removed for d in self.days):
                raise ValueError("The destination is already scheduled")
        return self


class WorkoutSet(StrictModel):
    weight_kg: Decimal | None = Field(default=None, ge=0, le=1000)
    reps: int | None = Field(default=None, ge=1, le=1000)
    completed: bool = False

    @model_validator(mode="after")
    def actual_values(self):
        if self.completed and (self.weight_kg is None or self.reps is None):
            raise ValueError("Completed sets require actual reps and weight (0 for bodyweight)")
        return self


class WorkoutExercise(StrictModel):
    key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    sets: list[WorkoutSet] = Field(min_length=1, max_length=30)
    target_sets: int | None = Field(default=None, ge=1, le=30)
    target_reps: int | None = Field(default=None, ge=1, le=1000)
    target_reps_max: int | None = Field(default=None, ge=1, le=1000)
    target_weight_kg: Decimal | None = Field(default=None, ge=0, le=1000)
    rest_seconds: int | None = Field(default=None, ge=0, le=1800)

    @model_validator(mode="after")
    def valid_rep_range(self):
        if self.target_reps_max is not None and (self.target_reps is None or self.target_reps_max < self.target_reps):
            raise ValueError("The upper rep target requires a lower target and cannot be smaller")
        return self


class WorkoutData(StrictModel):
    reported_duration_seconds: int | None = Field(default=None, ge=60, le=86400)
    finished_at: datetime | None = None
    effort: Literal["easy", "right", "hard"] | None = None
    name: str = Field(min_length=1, max_length=200)
    plan_day_key: str | None = Field(default=None, min_length=1, max_length=80)
    scheduled_date: date | None = None
    status: Literal["in_progress", "completed"] = "in_progress"
    duration_seconds: int = Field(default=0, ge=0, le=86400)
    current_exercise_index: int = Field(default=0, ge=0, le=30)
    exercises: list[WorkoutExercise] = Field(min_length=1, max_length=30)
    timer_started_at: datetime | None = None
    rest_ends_at: datetime | None = None
    paused_at: datetime | None = None

    @field_validator("timer_started_at", "rest_ends_at", "paused_at")
    @classmethod
    def aware_timer(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Workout timers require an explicit timezone")
        return value

    @model_validator(mode="after")
    def valid_progress(self):
        if (self.plan_day_key is None) != (self.scheduled_date is None):
            raise ValueError("A scheduled workout needs both day key and date")
        if len({exercise.key for exercise in self.exercises}) != len(self.exercises):
            raise ValueError("Exercise keys must be unique")
        if self.current_exercise_index > len(self.exercises):
            raise ValueError("Exercise cursor is outside the workout")
        has_actual_sets = any(s.completed for e in self.exercises for s in e.sets)
        if self.status == "completed" and not has_actual_sets:
            raise ValueError("Log at least one actual set before finishing the workout")
        if self.status == "completed":
            self.current_exercise_index = len(self.exercises)
            self.paused_at = None
            self.rest_ends_at = None
        return self


class MeasurementData(StrictModel):
    waist_cm: Decimal | None = Field(default=None, gt=0, le=400)
    chest_cm: Decimal | None = Field(default=None, gt=0, le=400)
    hips_cm: Decimal | None = Field(default=None, gt=0, le=400)
    arm_cm: Decimal | None = Field(default=None, gt=0, le=200)
    thigh_cm: Decimal | None = Field(default=None, gt=0, le=200)
    body_fat_percent: Decimal | None = Field(default=None, gt=0, lt=100)

    @model_validator(mode="after")
    def nonempty(self):
        if all(value is None for value in self.model_dump().values()):
            raise ValueError("At least one measurement is required")
        return self


class ProfileData(StrictModel):
    goal: Literal["weight_loss", "weight_gain", "maintain", "course", "custom"] = "weight_loss"
    custom_goal: str = Field(default="", max_length=500)
    age: int | None = Field(default=None, ge=18, le=120)
    sex: Literal["male", "female"] | None = None
    height_cm: Decimal | None = Field(default=None, ge=50, le=260)
    target_weight_kg: Decimal | None = Field(default=None, gt=0, le=500)
    activity: Literal["low", "light", "moderate", "high"] | None = None
    preferences: str = Field(default="", max_length=2000)
    restrictions: str = Field(default="", max_length=2000)
    lifestyle: str = Field(default="", max_length=2000)
    training_experience: str = Field(default="", max_length=2000)
    training_conditions: str = Field(default="", max_length=2000)
    onboarding_optional_step: int = Field(default=0, ge=0, le=6)
    onboarding_nutrition_reason: str = Field(default="", max_length=2000)
    nutrition: Nutrition | None = None
    nutrition_source: Literal["manual", "calculated"] = "manual"
    nutrition_rule_version: str | None = Field(default=None, max_length=80)
    workout_plan: WorkoutPlan | None = None


class OnboardingData(StrictModel):
    goal: Literal["weight_loss", "weight_gain", "maintain", "custom"]
    age: int = Field(ge=18, le=120)
    sex: Literal["male", "female"]
    height_cm: Decimal = Field(ge=50, le=260)
    current_weight_kg: Decimal = Field(gt=0, le=500)
    target_weight_kg: Decimal = Field(gt=0, le=500)
    activity: Literal["low", "light", "moderate", "high"]
    custom_goal: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def custom_goal_has_text(self):
        self.custom_goal = self.custom_goal.strip()
        if self.goal == "custom" and not self.custom_goal:
            raise ValueError("Расскажите о своей цели")
        if self.goal == "weight_loss" and self.target_weight_kg >= self.current_weight_kg:
            raise ValueError("Для снижения веса желаемый вес должен быть ниже текущего")
        if self.goal == "weight_gain" and self.target_weight_kg <= self.current_weight_kg:
            raise ValueError("Для набора веса желаемый вес должен быть выше текущего")
        return self


class OnboardingDetails(StrictModel):
    next_step: int = Field(ge=1, le=6)
    lifestyle: str | None = Field(default=None, max_length=2000)
    preferences: str | None = Field(default=None, max_length=2000)
    restrictions: str | None = Field(default=None, max_length=2000)
    training_experience: str | None = Field(default=None, max_length=2000)
    training_conditions: str | None = Field(default=None, max_length=2000)


class MobileReminders(StrictModel):
    topics: list[Literal["nutrition", "water", "meal_balance", "photo", "training", "rest", "unfinished",
                         "post_water", "reschedule", "program", "effort", "wellbeing", "energy", "bedtime",
                         "stress", "sleep"]] = Field(default_factory=list, max_length=16)
    water_time: time = time(15)
    workout_time: time = time(18)
    wellbeing_time: time = time(9)
    bedtime: time = time(22, 30)
    stress_time: time = time(20)
    effort_delay: int = Field(default=30, ge=5, le=240)
    short_sleep_hours: float = Field(default=7, gt=0, le=24)
    water_portion: int = Field(default=250, ge=1, le=2000)

    @field_validator("water_time", "workout_time", "wellbeing_time", "bedtime", "stress_time")
    @classmethod
    def wall_clock(cls, value):
        if value.tzinfo is not None:
            raise ValueError("Expected local time")
        return value


class Settings(StrictModel):
    mobile: MobileReminders = Field(default_factory=MobileReminders)
    timezone: str = "Europe/Moscow"
    nutrition_auto_eligible: bool = False
    course_reminders: bool = False
    daily_time: time | None = None
    weight_time: time | None = None
    weekly_time: time | None = None
    weekly_day: int = Field(default=6, ge=0, le=6)
    supply_reminders: bool = False
    supply_days: int = Field(default=7, ge=1, le=30)
    meal_reminders: list[Literal["breakfast", "lunch", "dinner"]] = Field(default_factory=list, max_length=3)
    water_goal_ml: int | None = Field(default=None, ge=250, le=10000)
    checkin_time: time | None = None
    inactivity_days: int | None = Field(default=None, ge=2, le=30)
    inactivity_time: time = time(18, 0)
    checkin_topics: list[Literal["course", "nutrition", "weight", "wellbeing"]] = Field(default_factory=lambda: ["course", "nutrition", "weight", "wellbeing"], max_length=4)

    @field_validator("daily_time", "weight_time", "weekly_time", "checkin_time", "inactivity_time")
    @classmethod
    def local_time_only(cls, value):
        if value is not None and value.tzinfo is not None:
            raise ValueError("Use a local time without offset; timezone is a separate setting")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        return normalize_timezone(value)


Unit = Literal["mg", "mcg", "g", "ml", "capsule", "tablet", "IU"]


class Stage(StrictModel):
    start_date: date
    end_date: date
    amount: Decimal = Field(gt=0, le=1000000)
    unit: Unit
    interval_days: int = Field(default=1, ge=1, le=365)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    times: list[time] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def check_schedule(self):
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 730:
            raise ValueError("Stage must span 0–730 days")
        if len(set(self.weekdays)) != len(self.weekdays) or any(v < 0 or v > 6 for v in self.weekdays):
            raise ValueError("Weekdays must be unique integers from 0 to 6")
        # Weekdays are the effective schedule whenever they are present. The
        # interval is ignored by the scheduler, so canonicalize model output
        # instead of rejecting an otherwise unambiguous course.
        if self.weekdays:
            self.interval_days = 1
        # PlanData.timezone is authoritative. RFC 3339 generators may append an
        # offset to a time-only value even though the value represents a local
        # wall clock time; remove that redundant offset and duplicate slots.
        self.times = list(dict.fromkeys(value.replace(tzinfo=None) for value in self.times))
        return self


class CourseItem(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    variant_id: int | None = Field(default=None, gt=0)
    stages: list[Stage] = Field(min_length=1, max_length=24)
    package_amount: Decimal | None = Field(default=None, gt=0, le=100000000)
    package_unit: Unit | None = None
    home_amount: Decimal | None = Field(default=None, ge=0, le=100000000)
    package_source_name: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def check_stages(self):
        stages = sorted(self.stages, key=lambda s: s.start_date)
        if any(a.end_date >= b.start_date for a, b in zip(stages, stages[1:])):
            raise ValueError("Stages of one position must not overlap")
        if bool(self.package_amount is not None) != bool(self.package_unit is not None):
            raise ValueError("Package amount requires a unit")
        return self


class PlanData(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    timezone: str = "Europe/Moscow"
    items: list[CourseItem] = Field(min_length=1, max_length=12)
    source: Literal["user_supplied_plan", "ai_recommended_plan"] = "user_supplied_plan"
    _zone = field_validator("timezone")(Settings.valid_timezone.__func__)


class EntryData(StrictModel):
    kind: Literal["meal", "water", "weight", "wellbeing", "workout", "measurement", "progress_photo"]
    occurred_at: datetime
    meal_type: Literal["breakfast", "lunch", "dinner", "extra"] | None = None
    meal_key: str | None = Field(default=None, min_length=1, max_length=64)
    water_ml: int | None = Field(default=None, gt=0, le=10000)
    food_photo_attachment_ids: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list, max_length=8)
    name: str | None = Field(default=None, max_length=300)
    portion_g: Decimal | None = Field(default=None, gt=0, le=100000)
    nutrition: Nutrition | None = None
    weight_kg: Decimal | None = Field(default=None, gt=0, le=500)
    wellbeing: int | None = Field(default=None, ge=1, le=5)
    appetite: int | None = Field(default=None, ge=1, le=5)
    energy: int | None = Field(default=None, ge=1, le=5)
    stress_change: Literal["calmer", "same", "tenser"] | None = None
    sleep_hours: Decimal | None = Field(default=None, ge=0, le=24)
    mood: int | None = Field(default=None, ge=1, le=3, description="1 low, 2 steady, 3 uplifted; self-reported")
    stress: int | None = Field(default=None, ge=1, le=5, description="1 calm through 5 very tense; self-reported")
    sleep_quality: int | None = Field(default=None, ge=1, le=3, description="1 poorly rested, 2 somewhat rested, 3 well rested")
    note: str = Field(default="", max_length=4000)
    estimated: bool = False
    assumptions: str = Field(default="", max_length=1500)
    favorite: bool = False
    workout: WorkoutData | None = None
    measurement: MeasurementData | None = None
    photo_attachment_ids: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def check_entry(self):
        if self.occurred_at.tzinfo is None:
            raise ValueError("Timestamp must include an offset")
        if self.kind == "meal" and (not self.name or self.nutrition is None):
            raise ValueError("Meal requires name and nutrition")
        if self.kind != "meal" and (self.meal_type is not None or self.meal_key is not None or self.food_photo_attachment_ids):
            raise ValueError("Meal metadata requires a meal")
        if self.meal_key is not None and self.meal_type != "extra":
            raise ValueError("Only additional meals have a group key")
        if self.kind == "water" and self.water_ml is None:
            raise ValueError("Water records require an amount in ml")
        if self.water_ml is not None and self.kind not in {"meal", "water"}:
            raise ValueError("Drinking water belongs to a meal or a water record")
        if self.kind == "water" and any(value is not None for value in (self.nutrition, self.portion_g, self.weight_kg, self.wellbeing, self.appetite, self.energy, self.sleep_hours)):
            raise ValueError("Water records cannot contain food or health measurements")
        if len(set(self.food_photo_attachment_ids)) != len(self.food_photo_attachment_ids):
            raise ValueError("Food photo IDs must be unique")
        if self.kind == "weight" and self.weight_kg is None:
            raise ValueError("Weight is required")
        if self.kind != "wellbeing" and any(v is not None for v in (self.mood, self.stress, self.sleep_quality, self.stress_change)):
            raise ValueError("Mood, stress and sleep quality belong to a wellbeing record")
        if self.kind == "wellbeing" and not self.note and all(v is None for v in (self.wellbeing, self.appetite, self.energy, self.sleep_hours, self.mood, self.stress, self.sleep_quality)):
            raise ValueError("A wellbeing value or note is required")
        for name in ("workout", "measurement"):
            if (getattr(self, name) is not None) != (self.kind == name):
                raise ValueError(f"{name} payload must match entry kind")
        if self.favorite and self.kind != "meal":
            raise ValueError("Only meals can be favorites")
        if bool(self.photo_attachment_ids) != (self.kind == "progress_photo"):
            raise ValueError("Progress photos require private image attachment IDs; other entries cannot contain them")
        if len(set(self.photo_attachment_ids)) != len(self.photo_attachment_ids):
            raise ValueError("Photo attachment IDs must be unique")
        if self.kind == "progress_photo" and (self.estimated or any(v is not None for v in (
            self.nutrition, self.portion_g, self.weight_kg, self.wellbeing, self.appetite, self.energy, self.sleep_hours,
        ))):
            raise ValueError("Progress photos cannot imply nutrition, weight or health measurements")
        return self


class Proposal(StrictModel):
    """The model proposes a draft. It cannot approve its own proposal."""
    kind: Literal["profile", "plan", "entry", "nutrition"]
    profile: ProfileData | None = None
    plan: PlanData | None = None
    entry: EntryData | None = None
    nutrition: Nutrition | None = None
    summary: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def exactly_one_payload(self):
        for name in ("profile", "plan", "entry", "nutrition"):
            if (getattr(self, name) is not None) != (name == self.kind):
                raise ValueError("Proposal must contain only its matching payload")
        return self


class Action(StrictModel):
    meal_estimate_request: str | None = Field(default=None, min_length=8, max_length=64)
    request_key: str = Field(min_length=8, max_length=64)
    record_now: bool = False
    kind: Literal["enable", "disable", "onboard", "onboarding_details", "profile", "settings", "plan", "plan_status", "workout_plan", "entry", "delete_entry", "event", "confirm", "cancel", "nutrition", "dialogue_confirm", "dialogue_cancel", "dialogue_undo", "dialogue_edit"]
    expected_version: int | None = Field(default=None, ge=1)
    resource_id: int | None = Field(default=None, gt=0)
    profile: ProfileData | None = None
    onboarding: OnboardingData | None = None
    onboarding_details: OnboardingDetails | None = None
    settings: Settings | None = None
    plan: PlanData | None = None
    workout_plan: WorkoutPlan | None = None
    entry: EntryData | None = None
    nutrition: Nutrition | None = None
    nutrition_rule_version: str | None = Field(default=None, max_length=80)
    status: Literal["active", "paused", "completed", "pending", "done", "skipped"] | None = None
    message_id: int | None = Field(default=None, gt=0)
    action_id: str | None = Field(default=None, max_length=120)
    action_token: str | None = Field(default=None, max_length=2000)
    consent_version: str | None = Field(default=None, max_length=80)
    adult_confirmed: bool = False
