from datetime import date, time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import Field, field_validator, model_validator
from src.app.services.ai.companion.schemas import StrictModel
from src.app.modules.telegram_ai.profile import Identity


class NutritionPreview(Identity):
    eligibility_confirmed: bool = False
    activity: Literal["low", "light", "moderate", "high"] | None = None


class NutritionEligibility(Identity):
    confirmed: bool


class EraseData(Identity):
    confirmed: Literal[True]


class NutritionTarget(StrictModel):
    kcal: float = Field(gt=0, le=10000, allow_inf_nan=False)
    protein: float | None = Field(default=None, ge=0, le=2000, allow_inf_nan=False)
    fat: float | None = Field(default=None, ge=0, le=2000, allow_inf_nan=False)
    carbs: float | None = Field(default=None, ge=0, le=2000, allow_inf_nan=False)
    source: Literal["user", "specialist"] = "user"


class Exercise(StrictModel):
    weekday: int = Field(ge=0, le=6)
    name: str = Field(min_length=1, max_length=120)
    sets: int = Field(ge=1, le=30)
    reps: int = Field(ge=1, le=200)


class Program(StrictModel):
    exercises: list[Exercise] = Field(min_length=1, max_length=100)


class WorkoutSet(StrictModel):
    # Preserve the public OpenAPI component name after moving the model.
    __module__ = "src.app.modules.telegram_ai.mentor"
    exercise: str = Field(min_length=1, max_length=120)
    weight_kg: float = Field(ge=0, le=1000, allow_inf_nan=False)
    reps: int = Field(ge=1, le=1000)


class Workout(StrictModel):
    sets: list[WorkoutSet] = Field(min_length=1, max_length=200)
    duration_minutes: float = Field(gt=0, le=1440, allow_inf_nan=False)
    active_entry_id: int | None = Field(default=None, gt=0)


class PhysicalActivity(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    duration_minutes: float = Field(gt=0, le=1440, allow_inf_nan=False)


class Course(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    source: Literal["user", "specialist"]
    dose_text: str = Field(min_length=1, max_length=240)
    timezone: str = Field(default="Europe/Moscow", max_length=80)
    start_date: date
    end_date: date
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    interval_days: int | None = Field(default=None, ge=1, le=365)
    times: list[str] = Field(min_length=1, max_length=8)
    supply_amount: float | None = Field(default=None, ge=0, le=1000000, allow_inf_nan=False)
    amount_per_intake: float | None = Field(default=None, gt=0, le=1000000, allow_inf_nan=False)
    supply_unit: str | None = Field(default=None, min_length=1, max_length=40)
    package_count: float | None = Field(default=None, ge=0, le=1000000, allow_inf_nan=False)
    package_amount: float | None = Field(default=None, gt=0, le=1000000, allow_inf_nan=False)
    package_unit: str | None = Field(default=None, max_length=40)
    intake_unit: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def schedule_valid(self):
        try: ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc: raise ValueError("Unknown timezone") from exc
        if not 0 <= (self.end_date-self.start_date).days <= 365: raise ValueError("Course must span at most 366 days")
        if len(set(self.weekdays)) != len(self.weekdays) or any(d not in range(7) for d in self.weekdays): raise ValueError("Weekdays must be unique, Monday=0 through Sunday=6")
        if bool(self.weekdays) == bool(self.interval_days): raise ValueError("Choose weekdays OR interval_days anchored to start_date")
        if len(set(self.times)) != len(self.times): raise ValueError("Duplicate course times")
        for value in self.times:
            parsed = time.fromisoformat(value)
            if len(value) != 5 or parsed.tzinfo is not None: raise ValueError("Expected HH:MM")
        supplied = [self.supply_amount, self.amount_per_intake, self.supply_unit, self.package_count,
            self.package_amount, self.package_unit, self.intake_unit]
        if any(x is not None for x in supplied):
            from src.app.modules.telegram_ai.course_inventory import normalize_supply
            normalized = normalize_supply(self.model_dump())
            for key in ("supply_amount", "amount_per_intake", "supply_unit"): setattr(self, key, normalized[key])
            for key in ("package_count", "package_amount", "package_unit", "intake_unit"): setattr(self, key, None)
        return self


class Measurement(StrictModel):
    waist_cm: float | None = Field(default=None, gt=0, le=300, allow_inf_nan=False)
    chest_cm: float | None = Field(default=None, gt=0, le=300, allow_inf_nan=False)
    hips_cm: float | None = Field(default=None, gt=0, le=300, allow_inf_nan=False)
    photo_file_id: str | None = Field(default=None, min_length=1, max_length=512)
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def nonempty(self):
        if not any((self.waist_cm, self.chest_cm, self.hips_cm, self.photo_file_id)): raise ValueError("Measurement or private Telegram photo required")
        return self


class Wellbeing(StrictModel):
    score: int = Field(ge=1, le=5)
    energy_score: int | None = Field(default=None, ge=1, le=5)
    note: str = Field(default="", max_length=2000)


MODELS = {"target": NutritionTarget, "program": Program, "workout": Workout, "activity_log": PhysicalActivity,
          "course": Course, "measurement": Measurement, "wellbeing": Wellbeing}


class RecordDraft(Identity):
    request_key: str = Field(min_length=8, max_length=128)
    expected_version: int | None = Field(default=None, ge=0)
    kind: Literal["target", "program", "workout", "activity_log", "course", "measurement", "wellbeing"]
    data: dict
    replaces_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def structured_data(self):
        self.data = MODELS[self.kind].model_validate(self.data).model_dump(mode="json")
        if self.kind == "workout" and self.data.get("active_entry_id") is None: self.data.pop("active_entry_id", None)
        return self


class RecordAction(Identity):
    entry_id: int = Field(gt=0)
    action: Literal["confirm", "cancel", "stop"]


class CourseAction(Identity):
    entry_id: int = Field(gt=0)
    action: Literal["done", "skipped"]


class MealLibrary(Identity):
    query: str = Field(default="", max_length=240)
    favorites_only: bool = False
    offset: int = Field(default=0, ge=0, le=100000)


class Favorite(Identity):
    entry_id: int = Field(gt=0)
    enabled: bool


class RepeatMeal(Identity):
    entry_id: int = Field(gt=0)
    request_key: str = Field(min_length=8, max_length=128)


class WorkoutStart(Identity):
    request_key: str = Field(min_length=8, max_length=128)


class SetInput(WorkoutStart):
    entry_id: int = Field(gt=0)
    exercise_set: WorkoutSet


class WorkoutFinish(Identity):
    entry_id: int = Field(gt=0)
    duration_minutes: float | None = Field(default=None, gt=0, le=1440, allow_inf_nan=False)


class RecordRead(Identity):
    entry_id: int = Field(gt=0)


class CourseEvents(RecordRead):
    offset: int = Field(default=0, ge=0, le=3000)
    limit: int = Field(default=10, ge=1, le=20)
    pending_only: bool = False


class CourseSupply(Identity):
    entry_id: int = Field(gt=0)
    request_key: str = Field(min_length=8, max_length=128)
    supply_amount: float = Field(ge=0, le=1000000, allow_inf_nan=False)
    amount_per_intake: float = Field(gt=0, le=1000000, allow_inf_nan=False)
    supply_unit: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def normalized(self):
        from src.app.modules.telegram_ai.course_inventory import normalize_supply
        result = normalize_supply(self.model_dump())
        self.supply_unit = result["supply_unit"]
        return self


class SupplyPreview(Identity):
    supply_amount: float | None = Field(default=None, ge=0, le=1000000, allow_inf_nan=False)
    amount_per_intake: float | None = Field(default=None, gt=0, le=1000000, allow_inf_nan=False)
    supply_unit: str | None = Field(default=None, max_length=40)
    package_count: float | None = Field(default=None, ge=0, le=1000000, allow_inf_nan=False)
    package_amount: float | None = Field(default=None, gt=0, le=1000000, allow_inf_nan=False)
    package_unit: str | None = Field(default=None, max_length=40)
    intake_unit: str | None = Field(default=None, max_length=40)


class CourseReminder(Identity):
    entry_id: int = Field(gt=0)
    reminder_time: str | None = None

    @field_validator("reminder_time")
    @classmethod
    def clock(cls, value):
        from src.app.modules.telegram_ai.journal import ReminderUpdate
        return ReminderUpdate.valid_clock(value)


class EstimateRecord(Identity):
    entry_id: int = Field(gt=0)


class Report(Identity):
    days: Literal[7, 30] = 7
