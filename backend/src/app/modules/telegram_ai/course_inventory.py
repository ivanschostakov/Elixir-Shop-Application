"""Inventory arithmetic for explicitly supplied quantities, never prescriptions."""
from decimal import Decimal

ALIASES = {
    "mg": "мг", "миллиграмм": "мг", "миллиграмма": "мг", "миллиграммов": "мг",
    "mcg": "мкг", "ug": "мкг", "микрограмм": "мкг", "микрограммов": "мкг",
    "g": "г", "грамм": "г", "грамма": "г", "граммов": "г",
    "ml": "мл", "миллилитр": "мл", "миллилитра": "мл", "миллилитров": "мл",
    "таблетки": "таблетка", "таблеток": "таблетка", "табл": "таблетка",
    "капсулы": "капсула", "капсул": "капсула", "капс": "капсула",
    "флакона": "флакон", "флаконов": "флакон", "ампулы": "ампула", "ампул": "ампула",
    "дозы": "доза", "доз": "доза", "капли": "капля", "капель": "капля",
    "впрыскивания": "впрыскивание", "впрыскиваний": "впрыскивание",
    "iu": "ме", "единиц": "ед", "единица": "ед", "штук": "шт", "штука": "шт",
}
UNITS = {"мг", "мкг", "г", "мл", "таблетка", "капсула", "флакон", "ампула", "доза", "капля", "впрыскивание", "ме", "ед", "шт"}
MASS = {"мкг": Decimal("0.001"), "мг": Decimal(1), "г": Decimal(1000)}


def unit(value):
    value = str(value or "").strip().casefold().rstrip(".")
    value = ALIASES.get(value, value)
    if value not in UNITS:
        raise ValueError("Уточните единицу запаса и расхода. Содержимое флакона укажите отдельно, например 10 мг.")
    return value


def normalize_supply(data):
    """Convert only named mass units or explicit package contents."""
    result = dict(data)
    if data.get("package_count") is not None:
        if data.get("package_amount") is None or not data.get("package_unit"):
            raise ValueError("Сколько средства содержится в одной упаковке? Например, 10 мг во флаконе.")
        stock = Decimal(str(data["package_count"])) * Decimal(str(data["package_amount"]))
        stock_unit = unit(data["package_unit"])
        if data.get("supply_amount") is not None:
            given_unit = unit(data.get("supply_unit"))
            given = Decimal(str(data["supply_amount"]))
            if given_unit != stock_unit or given != stock:
                raise ValueError("Количество упаковок и общий запас не совпадают. Уточните фактический остаток.")
    else:
        if data.get("supply_amount") is None:
            raise ValueError("Сколько средства осталось сейчас?")
        stock = Decimal(str(data["supply_amount"]))
        stock_unit = unit(data.get("supply_unit"))
    if data.get("amount_per_intake") is None:
        raise ValueError("Какой расход на один приём указан в вашей существующей схеме?")
    consumption = Decimal(str(data["amount_per_intake"]))
    intake_unit = unit(data.get("intake_unit") or data.get("supply_unit"))
    if intake_unit != stock_unit:
        if intake_unit not in MASS or stock_unit not in MASS:
            raise ValueError("Запас и расход указаны в разных единицах. Уточните их; концентрацию и дозировку бот не угадывает.")
        consumption = consumption * MASS[intake_unit] / MASS[stock_unit]
    if not stock.is_finite() or not consumption.is_finite() or not 0 <= stock <= 1000000 or not 0 < consumption <= 1000000:
        raise ValueError("Проверьте количество оставшегося средства и расход на один приём.")
    result.update(supply_amount=float(stock), amount_per_intake=float(consumption), supply_unit=stock_unit)
    return result


def calculate_supply(course, events, instant):
    normalized = normalize_supply(course.data)
    baseline = course.data.get("supply_measured_at")
    from datetime import datetime
    measured = datetime.fromisoformat(baseline) if baseline else course.occurred_at
    baseline_ids = course.data.get("supply_baseline_done")
    done = [e for e in events if e.status == "done" and
        (e.id not in baseline_ids if baseline_ids is not None else
         (datetime.fromisoformat(e.data["completed_at"]) if e.data.get("completed_at") else e.occurred_at) >= measured)]
    amount = Decimal(str(normalized["amount_per_intake"]))
    left = max(Decimal(0), Decimal(str(normalized["supply_amount"])) - len(done)*amount)
    count = int(left // amount)
    pending = sorted([e for e in events if e.status == "pending" and e.occurred_at >= instant], key=lambda e: e.occurred_at)
    return {"available": True, "remaining": float(left), "unit": normalized["supply_unit"],
        "intakes_available": count, "shortfall": float(max(Decimal(0), len(pending)*amount-left)),
        "runs_out_at": pending[count].occurred_at.isoformat() if count < len(pending) else None,
        "last_available_at": pending[min(count, len(pending))-1].occurred_at.isoformat() if count and pending else None}
