from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .timezones import normalize_timezone


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Nutrition(StrictModel):
    kcal: Decimal = Field(ge=0, le=100000)
    protein: Decimal = Field(ge=0, le=10000)
    fat: Decimal = Field(ge=0, le=10000)
    carbs: Decimal = Field(ge=0, le=10000)


class ProfileData(StrictModel):
    goal: Literal["weight_loss", "maintain", "course"] = "weight_loss"
    age: int | None = Field(default=None, ge=18, le=120)
    sex: Literal["male", "female"] | None = None
    height_cm: Decimal | None = Field(default=None, ge=50, le=260)
    target_weight_kg: Decimal | None = Field(default=None, gt=0, le=500)
    activity: Literal["low", "light", "moderate", "high"] | None = None
    preferences: str = Field(default="", max_length=2000)
    restrictions: str = Field(default="", max_length=2000)
    nutrition: Nutrition | None = None
    nutrition_source: Literal["manual", "calculated"] = "manual"
    nutrition_rule_version: str | None = Field(default=None, max_length=80)


class Settings(StrictModel):
    timezone: str = "Europe/Moscow"
    nutrition_auto_eligible: bool = False
    course_reminders: bool = False
    daily_time: time | None = None
    weight_time: time | None = None
    weekly_time: time | None = None
    weekly_day: int = Field(default=6, ge=0, le=6)
    supply_reminders: bool = False
    supply_days: int = Field(default=7, ge=1, le=30)
    checkin_time: time | None = None
    checkin_topics: list[Literal["course", "nutrition", "weight", "wellbeing"]] = Field(default_factory=lambda: ["course", "nutrition", "weight", "wellbeing"], max_length=4)

    @field_validator("daily_time", "weight_time", "weekly_time", "checkin_time")
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
        if self.weekdays and self.interval_days != 1:
            raise ValueError("Choose weekdays OR a day interval")
        if len(set(self.times)) != len(self.times) or any(t.tzinfo is not None for t in self.times):
            raise ValueError("Times must be unique local times without offset")
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
    source: Literal["user_supplied_plan"] = "user_supplied_plan"
    _zone = field_validator("timezone")(Settings.valid_timezone.__func__)


class EntryData(StrictModel):
    kind: Literal["meal", "weight", "wellbeing"]
    occurred_at: datetime
    name: str | None = Field(default=None, max_length=300)
    portion_g: Decimal | None = Field(default=None, gt=0, le=100000)
    nutrition: Nutrition | None = None
    weight_kg: Decimal | None = Field(default=None, gt=0, le=500)
    wellbeing: int | None = Field(default=None, ge=1, le=5)
    appetite: int | None = Field(default=None, ge=1, le=5)
    energy: int | None = Field(default=None, ge=1, le=5)
    sleep_hours: Decimal | None = Field(default=None, ge=0, le=24)
    note: str = Field(default="", max_length=3000)
    estimated: bool = False
    assumptions: str = Field(default="", max_length=1500)

    @model_validator(mode="after")
    def check_entry(self):
        if self.occurred_at.tzinfo is None:
            raise ValueError("Timestamp must include an offset")
        if self.kind == "meal" and (not self.name or self.nutrition is None):
            raise ValueError("Meal requires name and nutrition")
        if self.kind == "weight" and self.weight_kg is None:
            raise ValueError("Weight is required")
        if self.kind == "wellbeing" and not self.note and all(v is None for v in (self.wellbeing, self.appetite, self.energy, self.sleep_hours)):
            raise ValueError("A wellbeing value or note is required")
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
    request_key: str = Field(min_length=8, max_length=64)
    kind: Literal["enable", "disable", "profile", "settings", "plan", "plan_status", "entry", "delete_entry", "event", "confirm", "cancel", "nutrition", "dialogue_confirm", "dialogue_cancel", "dialogue_undo", "dialogue_edit"]
    expected_version: int | None = Field(default=None, ge=1)
    resource_id: int | None = Field(default=None, gt=0)
    profile: ProfileData | None = None
    settings: Settings | None = None
    plan: PlanData | None = None
    entry: EntryData | None = None
    nutrition: Nutrition | None = None
    nutrition_rule_version: str | None = Field(default=None, max_length=80)
    status: Literal["active", "paused", "completed", "pending", "done", "skipped"] | None = None
    message_id: int | None = Field(default=None, gt=0)
    action_id: str | None = Field(default=None, max_length=120)
    action_token: str | None = Field(default=None, max_length=2000)
    consent_version: str | None = Field(default=None, max_length=80)
    adult_confirmed: bool = False
