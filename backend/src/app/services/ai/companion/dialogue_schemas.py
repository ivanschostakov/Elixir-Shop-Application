"""V2 conversational protocol. No model-provided approval or database access."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from .schemas import StrictModel, EntryData, PlanData, ProfileData, Nutrition, Settings, Unit


class Intake(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    local_date: date
    occurred_at: datetime | None = None
    period: Literal["unknown", "morning", "afternoon", "evening", "night"] = "unknown"
    amount: Decimal | None = Field(default=None, gt=0, le=1000000)
    unit: Unit | None = None
    note: str = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def valid_intake(self):
        if self.occurred_at is not None and self.occurred_at.tzinfo is None:
            raise ValueError("Actual time needs an offset")
        if (self.amount is None) != (self.unit is None):
            raise ValueError("Actual amount requires a unit")
        return self


class DialogueOperation(StrictModel):
    kind: Literal["profile", "plan", "entry", "nutrition", "event", "intake", "settings", "plan_status", "delete_entry"]
    summary: str = Field(min_length=1, max_length=2000)
    # Verbatim evidence from the CURRENT user message. It is not authorization
    # for course/settings changes; those always require separate confirmation.
    evidence: str = Field(min_length=1, max_length=2000)
    certain: bool = False
    resource_id: int | None = Field(default=None, gt=0)
    expected_version: int | None = Field(default=None, ge=1)
    profile: ProfileData | None = None
    plan: PlanData | None = None
    entry: EntryData | None = None
    nutrition: Nutrition | None = None
    nutrition_rule_version: str | None = None
    settings: Settings | None = None
    remind_course: bool | None = None
    intake: Intake | None = None
    status: Literal["active", "paused", "completed", "pending", "done", "skipped"] | None = None

    @model_validator(mode="after")
    def matching_payload(self):
        for key in ("profile", "plan", "entry", "nutrition", "settings"):
            if (getattr(self, key) is not None) != (self.kind == key):
                raise ValueError("Only the matching operation payload is allowed")
        if self.kind == "intake" and self.intake is None:
            raise ValueError("Actual intake is required")
        if self.intake is not None and self.kind not in {"event", "intake"}:
            raise ValueError("Unexpected intake")
        if self.kind in {"event", "delete_entry"} and (self.resource_id is None or self.expected_version is None):
            raise ValueError("Read the record and its version first")
        if self.kind == "event" and self.status not in {"pending", "done", "skipped"}:
            raise ValueError("Invalid event status")
        if self.kind == "plan_status" and self.status not in {"paused", "completed"}:
            raise ValueError("Resume requires a confirmed updated plan")
        return self


class DialogueDraft(StrictModel):
    # Deliberately structured prose rather than arbitrary JSON / SQL. It may
    # contain incomplete information but is NEVER a confirmed course.
    kind: Literal["course", "profile", "entry", "settings"]
    collected: str = Field(max_length=10000)
    missing: list[str] = Field(default_factory=list, max_length=20)


class DialogueTurn(StrictModel):
    operations: list[DialogueOperation] = Field(default_factory=list, max_length=12)
    draft: DialogueDraft | None = None
    clear_draft: bool = False
