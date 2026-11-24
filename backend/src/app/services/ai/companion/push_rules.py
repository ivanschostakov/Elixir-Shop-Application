"""Evaluate mobile reminders against confirmed records in the user's local calendar."""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_CEILING
from hashlib import sha256

from .meals import MEAL_TYPES, meal_type, water_target
from .schemas import WorkoutPlan

MEALS = {"breakfast": "завтрак", "lunch": "обед", "dinner": "ужин"}
NUTRIENTS = {"protein": "белку", "kcal": "калориям", "fat": "жирам", "carbs": "углеводам"}
DEFAULT_MEALTIMES = {"breakfast": "08:00", "lunch": "13:00", "dinner": "19:00"}
MINUTE = timedelta(minutes=1)


@dataclass
class Notice:
    kind: str
    key: str
    due: datetime
    title: str
    body: str
    actions: tuple[str, ...]
    data: dict = field(default_factory=dict)
    grace: int = 60

    def content(self):
        return dict(kind=self.kind, title=self.title, body=self.body, actions=list(self.actions), data=self.data)


def nutrition_gap(target, meals, portions=1):
    result = {}
    for key in NUTRIENTS:
        goal = Decimal(str(target.get(key) or 0))
        logged = sum(Decimal(str(row.data["nutrition"][key])) for row in meals)
        delta = goal / portions - logged
        if delta > 0:
            result[key] = int(delta.to_integral_value(rounding=ROUND_CEILING))
    return result


def primary_gap(gaps, target):
    key = max(gaps, key=lambda k: gaps[k] / float(target[k]))
    return f"по {NUTRIENTS[key]}", f"{gaps[key]} {'ккал' if key == 'kcal' else 'г'}"


def nutrition_notices(profile, settings, now, zone, rows, habits, due_clock):
    topics = settings.mobile.topics
    day = now.astimezone(zone).date()
    todays = [r for r in rows if r.occurred_at.astimezone(zone).date() == day]
    meals = [r for r in todays if r.kind == "meal"]
    logged_water = sum(r.data.get("water_ml") or 0 for r in todays if r.kind in {"meal", "water"})
    water_left = max(0, water_target(profile) - logged_water)
    target = profile.data.get("nutrition") or {}
    for kind in MEAL_TYPES:
        label = MEALS[kind]
        group = [r for r in meals if meal_type(r, zone) == kind]
        habitual = habits.get(kind, {}).get("time")
        slot = due_clock(time.fromisoformat(habitual or DEFAULT_MEALTIMES[kind]))
        if slot is None:
            continue
        info = {"meal": kind}
        if not group:
            if kind in settings.meal_reminders and habitual:
                previous = [r for r in rows if r.kind == "meal" and r.occurred_at.astimezone(zone).date() == day - timedelta(days=1) and meal_type(r, zone) == kind]
                yield Notice("missing_meal", f"meal_{kind}:{day}", min(slot + 30 * MINUTE, due_clock(time(23, 59))), f"Пропустил {label}?",
                             "Если уже поел, добавь его в дневник.", ("log_meal", "repeat_meal") if previous else ("log_meal",), info)
            if "nutrition" in topics and target:
                gaps = nutrition_gap(target, meals)
                if gaps:
                    nutrient, amount = primary_gap(gaps, target)
                    yield Notice("daily_gap", f"gap:{day}:{kind}", slot - timedelta(minutes=20),
                                 f"До твоей цели {nutrient} осталось {amount}", f"Подобрать {label}?",
                                 ("suggest", "later"), {**info, "gaps": gaps}, grace=25)
            continue
        if "meal_balance" not in topics:
            continue
        # Group dishes before evaluating the one-third target. Also cap by what is left today.
        daily = nutrition_gap(target, meals)
        gaps = {k: min(v, daily[k]) for k, v in nutrition_gap(target, group, 3).items() if k in daily}
        meal_water = sum(r.data.get("water_ml") or 0 for r in group)
        water_gap = min(water_left, max(0, (water_target(profile) + 2) // 3 - meal_water))
        last = max(r.occurred_at for r in group)
        if gaps:
            nutrient, amount = primary_gap(gaps, target)
            yield Notice("meal_balance", f"balance:{day}:{kind}", last + 5 * MINUTE,
                         f"До цели {nutrient} за {label} осталось {amount}", "Подобрать, чем дополнить?",
                         ("suggest", "dismiss"), {**info, "gaps": gaps, "water_gap": water_gap}, grace=45)
        elif water_gap:
            ml = min(settings.mobile.water_portion, water_gap)
            yield Notice("meal_water", f"balance:{day}:{kind}", last + 5 * MINUTE,
                         f"До цели по воде за {label} осталось {water_gap} мл",
                         f"Записать {ml} мл воды?", ("water", "dismiss"), {**info, "ml": ml}, grace=45)
    if "water" in topics and water_left and (due := due_clock(settings.mobile.water_time)):
        ml = min(settings.mobile.water_portion, water_left)
        yield Notice("water", f"water:{day}", due, f"Не забудь выпить {ml} мл воды", "Внести воду в дневник?",
                     ("water", "later"), {"ml": ml})


def plan_signature(plan):
    return sha256(plan.model_dump_json().encode()).hexdigest()[:16]


def program_complete(plan, completions):
    """Count scheduled occurrences arithmetically, even for long programs."""
    if not plan or not plan.end_date:
        return False
    weeks, extra = divmod((plan.end_date - plan.start_date).days + 1, 7)
    tail = {(plan.start_date.weekday() + n) % 7 for n in range(extra)}
    count = sum(weeks * len(d.weekdays) + len(tail.intersection(d.weekdays)) for d in plan.days)
    done = {(when, key) for when, key in completions if any(d.key == key for d in plan.scheduled(when))}
    return count > 0 and len(done) == count


def workout_notices(profile, settings, now, zone, rows, due_clock):
    day = now.astimezone(zone).date()
    opts = settings.mobile
    plan = WorkoutPlan.model_validate(profile.data["workout_plan"]) if profile.data.get("workout_plan") else None
    sessions = [r for r in rows if r.kind == "workout"]
    today = [r for r in rows if r.occurred_at.astimezone(zone).date() == day]
    wellbeing = latest_field(today, "energy")
    clock = due_clock(opts.workout_time)
    if plan and clock:
        for block in plan.scheduled(day):
            if any(r.data["workout"].get("plan_day_key") == block.key and r.data["workout"].get("scheduled_date") == day.isoformat() for r in sessions):
                continue
            key = f"train:{day}:{block.key}"
            data = {"block": block.key, "date": day.isoformat(), "plan": plan_signature(plan)}
            if "energy" in opts.topics and wellbeing and wellbeing.data["energy"] <= 2:
                yield Notice("low_energy", key, clock, "Как сейчас с силами?", f"{block.name}. Открыть план или выбрать короткую тренировку?", ("plan", "short"), data)
            elif "training" in opts.topics:
                duration = f" · {block.duration_minutes} мин" if block.duration_minutes else ""
                yield Notice("training", key, clock, f"Сегодня — {block.name}", f"Упражнений: {len(block.exercises)}{duration}. Начнём?", ("plan", "later"), data)
            tomorrow = day + timedelta(days=1)
            if "reschedule" in opts.topics and (not plan.end_date or tomorrow <= plan.end_date) and not plan.scheduled(tomorrow):
                yield Notice("move", f"move:{day}:{block.key}", clock + timedelta(minutes=(block.duration_minutes or 45) + 45),
                             "Перенести тренировку на завтра?", block.name, ("move", "log_workout", "dismiss"), data, grace=120)
    for row in sessions:
        w = row.data["workout"]
        data = {"entry_id": row.id}
        if w["status"] == "in_progress":
            if "unfinished" not in opts.topics:
                continue
            done = sum(s["completed"] for e in w["exercises"] for s in e["sets"])
            if done:
                block = next((b for b in plan.days if b.key == w.get("plan_day_key")), None) if plan else None
                duration = block.duration_minutes if block and block.duration_minutes else 45
                yield Notice("unfinished", f"unfinished:{row.id}", max(row.occurred_at + duration * MINUTE, row.updated_at + 5 * MINUTE),
                             f"Сохранено подходов: {done}", "Продолжить тренировку или завершить с этим результатом?", ("continue", "finish"), data, grace=180)
            continue
        finished = datetime.fromisoformat(w["finished_at"]) if w.get("finished_at") else row.updated_at
        if finished.astimezone(zone).date() != day:
            continue
        if "post_water" in opts.topics:
            yield Notice("post_water", f"postwater:{row.id}", finished, "Пил воду на тренировке?", "Можно сразу добавить её в дневник.", ("water250", "water500", "other_water"), data)
        if "effort" in opts.topics and not w.get("effort"):
            yield Notice("effort", f"effort:{row.id}", finished + opts.effort_delay * MINUTE,
                         "Как тебе сегодняшняя нагрузка?", w["name"], ("easy", "right", "hard"), data)


def latest_field(rows, field):
    return max((r for r in rows if r.kind == "wellbeing" and r.data.get(field) is not None),
               key=lambda r: (r.occurred_at, r.id), default=None)


def wellbeing_notices(settings, now, zone, rows, due_clock, morning_followup):
    day = now.astimezone(zone).date()
    todays = [r for r in rows if r.kind == "wellbeing" and r.occurred_at.astimezone(zone).date() == day]
    opts = settings.mobile
    if (due := due_clock(opts.wellbeing_time)):
        if morning_followup and "sleep" in opts.topics and not latest_field(todays, "sleep_quality"):
            yield Notice("sleep", f"mood:{day}", due, "Удалось выспаться?", "Как прошла ночь?", ("rested", "partly", "poorly"))
        elif "wellbeing" in opts.topics and not todays:
            yield Notice("wellbeing", f"mood:{day}", due, "Как самочувствие сегодня?", "Можно начать с одной оценки.", ("checkin", "later"))
    sleep = latest_field(todays, "sleep_hours")
    if "bedtime" in opts.topics and sleep and float(sleep.data["sleep_hours"]) < opts.short_sleep_hours and (due := due_clock(opts.bedtime)):
        yield Notice("bedtime", f"bed:{day}", due, "Время готовиться ко сну", "Можно понемногу заканчивать дела на сегодня.", ("bed_later",))
    stress = latest_field(todays, "stress")
    if "stress" in opts.topics and stress and stress.data["stress"] >= 4 and (due := due_clock(opts.stress_time)):
        yield Notice("stress", f"stress:{day}", due, "Как проходит вечер?", "Стало немного спокойнее?", ("calmer", "same", "tenser"), {"entry_id": stress.id})
