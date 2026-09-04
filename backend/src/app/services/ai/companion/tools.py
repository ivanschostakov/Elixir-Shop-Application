from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select

from src.database.models.ai.companion import AICompanionEvent
from . import service
from .schemas import Settings
from .timezones import timezone_info


def function(name, description, properties=None):
    properties = properties or {}
    return {"type": "function", "name": name, "description": description, "strict": True, "parameters": {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}}


DATES = {"from_date": {"type": "string", "description": "Inclusive local date YYYY-MM-DD"}, "to_date": {"type": "string", "description": "Exclusive local date YYYY-MM-DD; at most 90 days after from_date"}}
COMPANION_TOOLS = [
    function("get_active_plan", "Read the user's current confirmed plan before discussing its schedule or quantities. Never invent or change a dose."),
    function("get_course_events", "Read scheduled events and actual marks. Missing marks are not missed doses.", DATES),
    function("get_entries", "Read confirmed diary entries, newest first, up to 200.", {**DATES, "kind": {"type": "string", "enum": ["meal", "weight", "wellbeing"]}}),
    function("get_progress_summary", "Get complete server-calculated totals for the period; do not sum a paginated diary.", DATES),
    function("calculate_course_supply", "Calculate package needs from the existing confirmed plan. This does not prescribe or buy anything.", {"days": {"type": "integer", "minimum": 1, "maximum": 90}}),
    function("calculate_nutrition_targets", "Get an optional server-calculated nutrition target. Requires a complete confirmed adult profile, recent weight and nutrition eligibility. User confirmation is still required."),
]


class CompanionToolExecutor:
    def __init__(self, db, user_id, shop=None, dialogue=False):
        self.db, self.user_id, self.shop = db, user_id, shop
        self.dialogue = dialogue
        self.calls = []

    async def execute(self, name, arguments=None):
        args = arguments or {}
        if self.dialogue:
            from .dialogue_tools import DIALOGUE_TOOLS, execute_dialogue_tool
            if name in {t["name"] for t in DIALOGUE_TOOLS}:
                result = await execute_dialogue_tool(self.db, self.user_id, name, args, self.shop is not None)
                self.calls.append({"tool_name": name, "ok": result.get("ok", False)})
                return result
        names = {t["name"] for t in COMPANION_TOOLS}
        if name not in names:
            if self.dialogue:
                return {"ok": False, "error": "tool_unavailable"}
            if self.shop:
                result = await self.shop.execute(name, args)
                self.calls = [*self.calls, *self.shop.calls[-1:]]
                return result
            return {"ok": False, "error": "tool_unavailable"}
        if name == "calculate_course_supply" and self.shop is None:
            return {"ok": False, "error": "commerce_unavailable"}
        profile = await service.profile_for(self.db, self.user_id)
        if profile is None or not profile.enabled:
            return {"ok": False, "error": "companion_disabled"}
        if not service.consent_is_current(await service.consent_for(self.db, self.user_id)):
            return {"ok": False, "error": "personal_data_not_confirmed", "message": "Чат уже работает. Предложите карточку по данным пользователя; согласие запрашивается только при первом сохранении. Сохранённый профиль и дневник пока недоступны."}
        try:
            if name == "get_active_plan":
                result = service.dump(await service.current_plan(self.db, self.user_id))
            elif name == "calculate_course_supply":
                days = int(args.get("days", 30))
                if not 1 <= days <= 90:
                    raise ValueError("Invalid period")
                result = await service.supply_for(self.db, self.user_id, days)
            elif name == "calculate_nutrition_targets":
                result = await service.nutrition_suggestion(self.db, self.user_id)
            else:
                start_date, end_date = date.fromisoformat(args["from_date"]), date.fromisoformat(args["to_date"])
                if not 0 < (end_date - start_date).days <= 90:
                    raise ValueError("Period must be 1–90 days")
                zone = timezone_info(Settings.model_validate(profile.settings).timezone)
                start, end = (datetime.combine(d, time.min, zone).astimezone(timezone.utc) for d in (start_date, end_date))
                if name == "get_progress_summary":
                    result = await service.summary_for(self.db, self.user_id, start, end)
                elif name == "get_entries":
                    if args.get("kind") not in {"meal", "weight", "wellbeing"}:
                        raise ValueError("Invalid diary kind")
                    rows = await service.entries_for(self.db, self.user_id, start, end, args["kind"])
                    result = {"entries": [service.dump(e) for e in rows], "limit": 200, "may_have_more": len(rows) == 200}
                else:
                    rows = list((await self.db.execute(select(AICompanionEvent).where(AICompanionEvent.user_id == self.user_id, AICompanionEvent.scheduled_at >= start, AICompanionEvent.scheduled_at < end, AICompanionEvent.status != "cancelled").order_by(AICompanionEvent.scheduled_at).limit(200))).scalars().all())
                    result = {"events": [service.dump(e) for e in rows], "limit": 200}
            self.calls.append({"tool_name": name, "ok": True})
            return {"ok": True, "data": result}
        except (KeyError, ValueError, TypeError):
            self.calls.append({"tool_name": name, "ok": False})
            return {"ok": False, "error": "invalid_arguments", "message": "Уточните период или параметры запроса."}
