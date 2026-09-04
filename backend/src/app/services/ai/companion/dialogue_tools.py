from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import or_, select, cast, Text

from src.database.models import Product, Variant
from src.database.models.ai.companion import AICompanionEntry, AICompanionEvent, AICompanionPlan
from . import service
from .domain import parse_package
from .schemas import Settings
from .timezones import timezone_info
from .tools import function


DIALOGUE_TOOLS = [
    function("match_course_products", "Match ONLY products the user already takes; never prescribe or sell. Clarify ambiguous variants; no match permits an unlinked item.", {"query": {"type": "string", "minLength": 2, "maxLength": 200}}),
    function("list_course_history", "List the user's latest 30 course versions for selecting a previous course."),
    function("get_course_report", "Complete course report across every revision, through now. Null plan_id selects current course.", {"plan_id": {"type": ["integer", "null"]}}),
    function("find_companion_records", "Find owned diary records to edit/delete; returns IDs and versions, never aggregate totals.", {
        "kind": {"type": "string", "enum": ["meal", "weight", "wellbeing", "intake", "all"]},
        "from_date": {"type": "string"}, "to_date": {"type": "string"}, "query": {"type": "string", "maxLength": 200},
    }),
]


async def course_report(db, user_id, plan_id=None):
    plan = await db.get(AICompanionPlan, plan_id) if plan_id else await service.current_plan(db, user_id)
    if plan is None or plan.user_id != user_id:
        return {"available": False, "reason": "Курс не найден. Пришлите существующую схему в чат."}
    versions = list((await db.execute(select(AICompanionPlan).where(AICompanionPlan.user_id == user_id, AICompanionPlan.course_key == plan.course_key).order_by(AICompanionPlan.version))).scalars())
    now = service.now_utc()
    events = list((await db.execute(select(AICompanionEvent).where(AICompanionEvent.user_id == user_id, AICompanionEvent.plan_id.in_([v.id for v in versions]), AICompanionEvent.status != "cancelled", AICompanionEvent.scheduled_at <= now))).scalars())
    counts = {status: sum(e.status == status for e in events) for status in ("done", "skipped", "pending")}
    zone = timezone_info(Settings.model_validate((await service.profile_for(db, user_id)).settings).timezone)
    start_date = min(date.fromisoformat(s["start_date"]) for v in versions for i in v.data["items"] for s in i["stages"])
    start = datetime.combine(start_date, time.min, timezone_info(versions[0].data["timezone"]))
    summary = await service.summary_for(db, user_id, start, now) if start <= now else None
    return {"available": True, "plan_id": plan.id, "name": plan.data["name"], "status": plan.status, "versions": len(versions), "from_date": start.astimezone(zone).date().isoformat(), "to_date": now.astimezone(zone).date().isoformat(), "events": counts, "progress": summary,
            "note": "Отметки курса объединены по всем версиям. Питание и вес — общий дневник за этот период, не доказательство действия препарата."}


async def execute_dialogue_tool(db, user_id, name, args, allow_commerce):
    profile = await service.profile_for(db, user_id)
    if not profile or not profile.enabled:
        return {"ok": False, "error": "companion_disabled"}
    if name == "match_course_products":
        if not allow_commerce:
            return {"ok": False, "error": "commerce_unavailable"}
        query = str(args.get("query", "")).strip()
        if not 2 <= len(query) <= 200:
            return {"ok": False, "error": "invalid_query"}
        # No descriptions, price, stock or purchase links are exposed by this tool.
        term = query.replace("%", "\\%").replace("_", "\\_")
        rows = (await db.execute(select(Variant, Product).join(Product, Variant.product_id == Product.id).where(
            Product.archived.is_(False), Variant.archived.is_(False),
            or_(Product.name.ilike(f"%{term}%"), Variant.name.ilike(f"%{term}%"), Variant.sku.ilike(f"%{term}%")),
        ).order_by(Product.id, Variant.id).limit(13))).all()
        return {"ok": True, "data": {"candidates": [{"variant_id": v.id, "product_name": p.name, "variant_name": v.name, "package": parse_package(p.name, v.name)} for v, p in rows[:12]], "has_more": len(rows) > 12}}
    if not service.consent_is_current(await service.consent_for(db, user_id)):
        return {"ok": False, "error": "personal_data_not_confirmed"}
    try:
        if name == "list_course_history":
            plans = list((await db.execute(select(AICompanionPlan).where(AICompanionPlan.user_id == user_id).order_by(AICompanionPlan.id.desc()).limit(30))).scalars())
            data = [{"id": p.id, "course_key": p.course_key, "version": p.version, "name": p.data["name"], "status": p.status, "is_current": p.is_current} for p in plans]
        elif name == "get_course_report":
            data = await course_report(db, user_id, args.get("plan_id"))
        else:
            first, last = date.fromisoformat(args["from_date"]), date.fromisoformat(args["to_date"])
            if not 0 < (last - first).days <= 731 or args["kind"] not in {"meal", "weight", "wellbeing", "intake", "all"}:
                raise ValueError("Invalid period or kind")
            zone = timezone_info(Settings.model_validate(profile.settings).timezone)
            stmt = select(AICompanionEntry).where(AICompanionEntry.user_id == user_id, AICompanionEntry.occurred_at >= datetime.combine(first, time.min, zone), AICompanionEntry.occurred_at < datetime.combine(last, time.min, zone))
            if args["kind"] != "all": stmt = stmt.where(AICompanionEntry.kind == args["kind"])
            if args.get("query"):
                stmt = stmt.where(cast(AICompanionEntry.data, Text).ilike("%" + args["query"].replace("%", "\\%").replace("_", "\\_") + "%"))
            rows = list((await db.execute(stmt.order_by(AICompanionEntry.occurred_at.desc(), AICompanionEntry.id.desc()).limit(51))).scalars())
            data = {"entries": [service.dump(e) for e in rows[:50]], "has_more": len(rows) > 50}
        return {"ok": True, "data": data}
    except (KeyError, ValueError, TypeError, HTTPException):
        return {"ok": False, "error": "invalid_arguments", "message": "Уточните период или запись."}


async def quick_report(db, user_id, kind, days=7):
    """Plain-text report, computed without a model and stored in chat history."""
    if kind == "course":
        data = await course_report(db, user_id)
        if not data["available"]: return data["reason"]
        events = data["events"]
        text = f"Отчёт по курсу «{data['name']}»\n{data['from_date']} — {data['to_date']}\nВыполнено: {events['done']} · пропущено: {events['skipped']} · без отметки: {events['pending']}."
        if data["progress"] and data["progress"]["weight_change_kg"] is not None:
            text += f"\nИзменение внесённого веса за период: {data['progress']['weight_change_kg']} кг."
        return text + "\n" + data["note"]
    profile = await service.profile_for(db, user_id)
    zone = timezone_info(Settings.model_validate(profile.settings).timezone)
    now = service.now_utc()
    midnight = now.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    start = midnight if kind == "nutrition" else midnight - timedelta(days=days - 1)
    summary = await service.summary_for(db, user_id, start, now)
    text = "Питание сегодня" if kind == "nutrition" else f"Прогресс за {days} дней"
    n = summary["nutrition"]
    text += f"\nЗаписей еды: {summary['meals_logged']}; дней с записями: {summary['days_with_meals']}.\n{n['kcal']} ккал · Б {n['protein']} · Ж {n['fat']} · У {n['carbs']} г."
    if kind != "nutrition":
        text += f"\nИзмерений веса: {summary['weight_measurements']}."
        text += f" Изменение: {summary['weight_change_kg']} кг." if summary["weight_change_kg"] is not None else " Для динамики нужны хотя бы два измерения."
    return text + "\n" + summary["coverage_note"]
