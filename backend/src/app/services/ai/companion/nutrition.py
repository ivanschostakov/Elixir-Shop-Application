"""Versioned product defaults, not a prescription or an AI-generated formula.

Rationale and source links: docs/ai-companion-implementation.md#правила-питания.
"""
import json
from decimal import Decimal, DecimalException, ROUND_CEILING, ROUND_HALF_UP
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .schemas import Nutrition, ProfileData, StrictModel


class NutritionRules(StrictModel):
    version: str = Field(min_length=1, max_length=80)
    enabled: bool
    activity: dict[Literal["low", "light", "moderate", "high"], Annotated[Decimal, Field(ge=1, le=2)]]
    loss_fraction: Decimal = Field(ge=0, le=Decimal("0.20"))
    max_deficit_kcal: Decimal = Field(ge=0, le=500)
    kcal_floor: dict[Literal["male", "female"], Annotated[Decimal, Field(ge=1500, le=2500)]]
    max_kcal: Decimal = Field(ge=2500, le=6000)
    protein_fraction: Decimal = Field(ge=Decimal("0.10"), le=Decimal("0.30"))
    fat_fraction: Decimal = Field(ge=Decimal("0.20"), le=Decimal("0.35"))
    carbs_fraction: Decimal = Field(ge=Decimal("0.45"), le=Decimal("0.65"))

    @model_validator(mode="after")
    def complete_and_balanced(self):
        if set(self.activity) != {"low", "light", "moderate", "high"} or set(self.kcal_floor) != {"male", "female"}:
            raise ValueError("All activity levels and calorie floors are required")
        if self.protein_fraction + self.fat_fraction + self.carbs_fraction != 1:
            raise ValueError("Macronutrient energy fractions must add up to one")
        if self.kcal_floor["male"] < 1800:
            raise ValueError("Automatic male targets must be at least 1800 kcal")
        return self


DEFAULT_NUTRITION_RULES = NutritionRules(
    version="balanced-adult-v1", enabled=True,
    activity={"low": "1.2", "light": "1.375", "moderate": "1.55", "high": "1.725"},
    loss_fraction="0.15", max_deficit_kcal=500,
    kcal_floor={"female": 1500, "male": 1800}, max_kcal=4000,
    protein_fraction="0.25", fat_fraction="0.30", carbs_fraction="0.45",
)


def unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason}


def calculate_nutrition(profile: ProfileData, weight_kg: Decimal, rules_json: str = "", *, eligibility_confirmed: bool = False) -> dict:
    if not eligibility_confirmed:
        return unavailable("В разделе КБЖУ подтвердите отсутствие ограничений для авторасчёта. При беременности, ГВ, РПП или необходимости лечебного питания используйте ориентир специалиста.")
    if any(v is None for v in (profile.age, profile.sex, profile.height_cm, profile.activity)):
        return unavailable("Нужны возраст, пол, рост и активность.")
    if not weight_kg.is_finite() or not 0 < weight_kg <= 500:
        return unavailable("Проверьте текущий вес.")
    try:
        if rules_json.strip():
            data = json.loads(rules_json)
            # A short explicit opt-out is allowed; malformed overrides never use defaults.
            if isinstance(data, dict) and (data.get("enabled") is False or data.get("approved") is False):
                return unavailable("Авторасчёт отключён. Можно внести готовые КБЖУ вручную.")
            rules = NutritionRules.model_validate(data)
        else:
            rules = DEFAULT_NUTRITION_RULES
        if not rules.enabled:
            return unavailable("Авторасчёт отключён. Можно внести готовые КБЖУ вручную.")

        height_m2 = (profile.height_cm / 100) ** 2
        bmi = weight_kg / height_m2
        if bmi < Decimal("18.5") or (profile.target_weight_kg is not None and profile.target_weight_kg / height_m2 < Decimal("18.5")):
            return unavailable("Текущий или целевой вес ниже диапазона авторасчёта. Нужен индивидуальный ориентир специалиста.")
        if profile.goal == "weight_loss":
            if bmi < 25:
                return unavailable("При ИМТ ниже 25 автоматический дефицит не предлагаем. Выберите поддержание или внесите индивидуальные КБЖУ.")
            if profile.target_weight_kg is not None and profile.target_weight_kg >= weight_kg:
                return unavailable("Целевой вес уже достигнут или выше текущего. Уточните цель или выберите поддержание.")

        bmr = 10 * weight_kg + Decimal("6.25") * profile.height_cm - 5 * profile.age + (5 if profile.sex == "male" else -161)
        maintenance = bmr * rules.activity[profile.activity]
        deficit = min(maintenance * rules.loss_fraction, rules.max_deficit_kcal) if profile.goal == "weight_loss" else Decimal(0)
        floor = rules.kcal_floor[profile.sex]
        if maintenance < floor or (profile.goal == "weight_loss" and maintenance == floor):
            return unavailable("Расчёт слишком низкий для стандартного режима. Используйте индивидуальный ориентир специалиста.")
        target = max(floor, maintenance - deficit)
        if target > rules.max_kcal:
            return unavailable("Расчёт выше диапазона стандартного режима. Проверьте данные или внесите индивидуальный ориентир.")
        kcal = target.quantize(Decimal(1), rounding=ROUND_CEILING if profile.goal == "weight_loss" else ROUND_HALF_UP)
        if profile.goal == "weight_loss" and kcal >= maintenance:
            return unavailable("В пределах стандартного режима дефицит не получается. Выберите поддержание или индивидуальный ориентир.")
        nutrition = Nutrition(
            kcal=kcal,
            protein=(kcal * rules.protein_fraction / 4).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
            fat=(kcal * rules.fat_fraction / 9).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
            carbs=(kcal * rules.carbs_fraction / 4).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
        )
        return {
            "available": True, "nutrition": nutrition.model_dump(mode="json"), "rule_version": rules.version,
            "maintenance_kcal": str(round(maintenance)), "deficit_kcal": str(round(maintenance - kcal)),
            "note": "Стартовый ориентир по формуле Миффлина — Сан Жеора, не медицинское назначение. "
                    + ("Дефицит уменьшен из-за нижней границы калорий. " if target > maintenance - deficit else "")
                    + "Проверьте значения перед сохранением. Они не меняются автоматически при новых записях веса.",
        }
    except (ValueError, TypeError, KeyError, DecimalException):
        return unavailable("Настройки авторасчёта некорректны. Можно внести готовые КБЖУ вручную.")
