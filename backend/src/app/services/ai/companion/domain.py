"""Deterministic calculations. Nothing here selects a therapy or a dose."""
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from zoneinfo import ZoneInfo

from .schemas import PlanData
from .nutrition import calculate_nutrition

UNITS = {"мг": "mg", "mg": "mg", "мкг": "mcg", "mcg": "mcg", "µg": "mcg", "г": "g", "g": "g", "мл": "ml", "ml": "ml", "ме": "IU", "iu": "IU", "капсул": "capsule", "капсулы": "capsule", "капсула": "capsule", "capsules": "capsule", "capsule": "capsule", "таблеток": "tablet", "таблетки": "tablet", "tablets": "tablet", "tablet": "tablet"}
AMOUNT = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*(мкг|mcg|µg|мг|mg|мл|ml|капсулы|капсула|капсул|capsules?|таблеток|таблетки|tablets?|ме|iu|г|g)(?!\w)", re.I)


def parse_package(product_name: str, variant_name: str) -> dict:
    names = [n.strip() for n in (product_name, variant_name) if n.strip()]
    found = set()
    for name in names:
        matches = AMOUNT.findall(name)
        if len(matches) > 1 or re.search(r"[/+×]|\b(?:per|по)\b|\d\s*[xх]\s*\d", name, re.I):
            return {"known": False, "reason": "Состав смеси, концентрация или число упаковок требуют уточнения."}
        found.update((str(Decimal(amount.replace(",", "."))), UNITS[unit.lower()]) for amount, unit in matches)
    if len(found) != 1:
        return {"known": False, "reason": "Не удалось однозначно определить содержимое упаковки."}
    amount, unit = found.pop()
    # Strength alone is not the total contents of a bottle of capsules/tablets.
    if unit in {"mg", "mcg", "g"} and re.search(r"капсул|таблет|capsul|tablet", " ".join(names), re.I):
        return {"known": False, "reason": "Указана сила одной дозы; уточните число капсул/таблеток."}
    if Decimal(amount) <= 0:
        return {"known": False, "reason": "Содержимое должно быть положительным."}
    return {"known": True, "amount": amount, "unit": unit, "source_name": " / ".join(names)}


def convert_amount(amount: Decimal, source: str, target: str) -> Decimal:
    factors = {"mcg": Decimal("0.001"), "mg": Decimal(1), "g": Decimal(1000)}
    if source == target:
        return amount
    if source in factors and target in factors:
        return amount * factors[source] / factors[target]
    raise ValueError("Несовместимые единицы: требуется подтверждённый коэффициент, расчёт недоступен.")


def package_count(required: Decimal, home: Decimal, capacity: Decimal) -> int:
    if required < 0 or home < 0 or capacity <= 0:
        raise ValueError("Invalid supply quantities")
    return int((max(Decimal(0), required - home) / capacity).to_integral_value(rounding=ROUND_CEILING))


def schedule_events(plan: PlanData) -> list[dict]:
    zone = ZoneInfo(plan.timezone)
    events = []
    for item_index, item in enumerate(plan.items):
        for stage_index, stage in enumerate(item.stages):
            day = stage.start_date
            while day <= stage.end_date:
                eligible = day.weekday() in stage.weekdays if stage.weekdays else (day - stage.start_date).days % stage.interval_days == 0
                if eligible:
                    for local_time in sorted(stage.times):
                        local = datetime.combine(day, local_time, tzinfo=zone)
                        utc = local.astimezone(timezone.utc)
                        if utc.astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None):
                            raise ValueError("Время попало в переход часового пояса; уточните расписание.")
                        events.append({"event_key": f"{item_index}:{stage_index}:{day}:{local_time.isoformat()}", "scheduled_at": utc, "data": {"item_index": item_index, "stage_index": stage_index, "name": item.name, "amount": str(stage.amount), "unit": stage.unit}})
                        if len(events) > 5000:
                            raise ValueError("Слишком много событий; сократите период курса.")
                day += timedelta(days=1)
    return sorted(events, key=lambda e: e["scheduled_at"])

