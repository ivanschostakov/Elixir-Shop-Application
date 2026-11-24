import { mentorNumber } from "@/i18n/mentor-translations"
import { companionCalendarDay } from "@/screens/chat/companion-timezones"
import { numeric } from "@/screens/chat/mentor-data"
import type { CompanionState } from "@/services/api/companion"
export type MentorQuickStep = "weight" | "workouts" | "wellbeing" | "course"

export function nutritionFraction(amount: unknown, target: unknown): number {
    const value = numeric(amount), total = numeric(target)
    return value !== null && total !== null && total > 0 ? Math.max(0, Math.min(1, value / total)) : 0
}

export function mentorHomeNumber(value: unknown): string {
    const number = numeric(value)
    return number === null ? "—" : mentorNumber(number)
}

export function mentorHomeData(state: CompanionState | null, clock: string, now = new Date()) {
    const server = Date.parse(state?.as_of ?? "")
    if (Number.isFinite(server) && state?.received_at != null) now = new Date(server + Math.max(0, now.getTime() - state.received_at))
    const date = companionCalendarDay(now.toISOString(), clock)
    const dashboard = state?.mentor?.today?.date === date ? state.mentor.today : null
    const entries = (state?.entries ?? []).filter(entry => {
        const time = Date.parse(entry.occurred_at)
        return Number.isFinite(time) && time <= now.getTime() && companionCalendarDay(entry.occurred_at, clock) === date
    }).sort((a, b) => Date.parse(a.occurred_at) - Date.parse(b.occurred_at) || a.id - b.id)
    const meals = entries.filter(entry => entry.kind === "meal")
    const wellbeing = entries.filter(entry => entry.kind === "wellbeing").at(-1) ?? null
    const tasks = dashboard?.tasks ?? []
    const workouts = tasks.filter(task => task.kind === "workout")
    const nextCourse = state?.plan?.status === "active" ? (state.events ?? []).filter(event => event.status === "pending" && Date.parse(event.scheduled_at) > now.getTime())
        .sort((a, b) => Date.parse(a.scheduled_at) - Date.parse(b.scheduled_at) || a.id - b.id)[0] ?? null : null
    const nutrition = dashboard?.nutrition ?? null
    const target = nutrition?.target ?? state?.profile?.data.nutrition ?? null
    const consumed = nutrition?.consumed ?? null
    const targetCalories = numeric(target?.kcal), consumedCalories = numeric(consumed?.kcal)
    const remaining = targetCalories !== null && consumedCalories !== null ? targetCalories - consumedCalories : null
    const latest = state?.mentor?.latest_weight
    const weightToday = entries.some(entry => entry.kind === "weight") || !!latest && Number.isFinite(Date.parse(latest.occurred_at)) && companionCalendarDay(latest.occurred_at, clock) === date || !!dashboard && (state?.today?.weight_measurements ?? 0) > 0
    const wellbeingToday = !!wellbeing || !!dashboard && (state?.today?.wellbeing?.entries ?? 0) > 0
    const dueCourse = tasks.some(task => task.kind === "course" && task.status === "pending" && task.scheduled_at && Date.parse(task.scheduled_at) <= now.getTime())
    const quickStep: MentorQuickStep | null = !dashboard ? null : dueCourse ? "course" : !wellbeingToday ? "wellbeing" : !weightToday ? "weight" : workouts.some(task => task.status === "pending" || task.status === "in_progress") ? "workouts" : null
    const mealDueAt = Date.parse(nutrition?.missing_meal_due_at ?? "")
    const badges = {
        nutrition: now.getTime() >= mealDueAt,
        workouts: workouts.some(task => task.status === "pending" || task.status === "in_progress"),
        wellbeing: !!dashboard && !wellbeingToday,
    }
    return { date, instant: now.toISOString(), meals, wellbeing, workouts, nextCourse, target, consumed, remaining, quickStep, badges, mealDueAt,
        optionalIncomplete: (state?.profile?.data.onboarding_optional_step ?? 0) < 6 }
}
