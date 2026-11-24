import * as Notifications from "expo-notifications"
import * as SecureStore from "expo-secure-store"
import { AppState, Platform } from "react-native"
import type { CompanionEntry, CompanionState } from "@/services/api/companion"
import { mentorText as mt } from "@/i18n/mentor-translations"

export const actionLabels: Record<string, string> = {
    suggest: "Подобрать", later: "Позже", dismiss: "Оставить как есть", water: "Выпил", log_meal: "Записать",
    repeat_meal: "Повторить вчерашний", review: "Проверить", water250: "250 мл", water500: "500 мл", other_water: "Другой объём",
    plan: "Открыть план", short: "Короткий вариант", continue: "Продолжить", extend: "Ещё 30 секунд", restart: "Начать заново",
    close_empty: "Закрыть", finish: "Завершить", move: "Перенести", log_workout: "Уже тренировался", repeat_plan: "Повторить программу",
    new_plan: "Составить новую", checkin: "Отметить", bed_later: "Ещё 15 минут", calmer: "Спокойнее", same: "Без изменений",
    tenser: "Напряжённее", easy: "Легко", right: "В самый раз", hard: "Тяжело", rested: "Да", partly: "Частично", poorly: "Нет",
}
const categories = [
    ["suggest", "later"], ["suggest"], ["suggest", "dismiss"], ["water", "later"], ["water"], ["water", "dismiss"],
    ["log_meal", "repeat_meal"], ["log_meal"], ["review"], ["water250", "water500", "other_water"],
    ["plan", "later"], ["plan"], ["plan", "short"], ["continue", "extend"], ["restart", "close_empty"],
    ["continue", "finish"], ["move", "log_workout", "dismiss"], ["repeat_plan", "new_plan"],
    ["checkin", "later"], ["checkin"], ["bed_later"], ["calmer", "same", "tenser"], ["easy", "right", "hard"], ["rested", "partly", "poorly"],
]
let registeredLabels = ""
export async function registerMentorCategories() {
    if (Platform.OS === "web") return
    const labels = mt("Позже")
    if (labels === registeredLabels) return
    // iOS replaces its entire set of registered categories on each call.
    for (const actions of categories) {
        await Notifications.setNotificationCategoryAsync("mentor_" + actions.join("_"),
            actions.map(id => ({ identifier: id, buttonTitle: mt(actionLabels[id]), options: { opensAppToForeground: true } })))
    }
    registeredLabels = labels
}

// The OS owns the short rest timer while JS is suspended. Only reconcile reminders
// belonging to Mentor; changing an account or cancelling a set clears its timers.
const prefix = "mentor-session-"
const emptyHistoryKey = "mentor_empty_timers_v1"
let latest: CompanionState | null = null
let queue: Promise<void> = Promise.resolve()
let subscribed = false
let backgroundSince = Date.now()

export function syncMentorSessionTimers(state: CompanionState | null) {
    if (Platform.OS === "web") return Promise.resolve()
    latest = state
    if (!subscribed) {
        subscribed = true
        AppState.addEventListener("change", next => {
            if (next !== "active" && next !== "background") return
            if (next === "background") backgroundSince = Date.now()
            void syncMentorSessionTimers(latest).catch(() => undefined)
        })
    }
    queue = queue.catch(() => undefined).then(reconcile)
    return queue
}

async function reconcile() {
    const state = latest, profile = state?.profile
    const topics = !state?.consent_required && profile?.enabled ? profile.settings.mobile?.topics ?? [] : []
    const pending = (await Notifications.getAllScheduledNotificationsAsync()).filter(n => n.identifier.startsWith(prefix))
    const wanted = new Map<string, { due: number; title: string; body: string; categoryIdentifier: string; key: string; kind: string }>()
    const now = Date.now()
    const serverAt = Date.parse(state?.as_of ?? "")
    const offset = state?.received_at && Number.isFinite(serverAt) ? state.received_at - serverAt : 0
    const existing = new Set(pending.map(n => n.identifier))
    // Keep the deadline across process restarts. A delivered empty-session prompt
    // stays consumed until the user records or restarts that session.
    const raw = await SecureStore.getItemAsync(emptyHistoryKey)
    const history: Record<string, number> = raw ? JSON.parse(raw) : {}
    const nextHistory: Record<string, number> = {}
    for (const r of (state?.open_workouts ?? state?.entries ?? []) as CompanionEntry[]) {
        const w = r.data.workout
        if (!profile || !w || w.status !== "in_progress") continue
        const rest = Date.parse(w.rest_ends_at ?? "")
        if (topics.includes("rest") && !w.paused_at && rest + offset > now) {
            const key = `rest:${r.id}:${rest}`
            const exercise = w.exercises.slice(w.current_exercise_index).find(e => e.sets.some(s => !s.completed))
            const next = exercise ? exercise.sets.findIndex(s => !s.completed) + 1 : 0
            wanted.set(prefix + profile.id + "-" + key, { due: rest + offset, key, kind: "rest", title: "Отдых закончился",
                body: exercise ? `${exercise.name} · подход ${next} из ${exercise.sets.length}` : "Можно продолжить тренировку.", categoryIdentifier: "mentor_continue_extend" })
        }
        if (topics.includes("unfinished") && !w.reported_duration_seconds && !w.exercises.some(e => e.sets.some(s => s.completed))) {
            const key = `empty:${r.id}:${r.version}`
            const id = prefix + profile.id + "-" + key
            if (history[id] && history[id] <= now) { nextHistory[id] = history[id]; continue }
            if (AppState.currentState !== "background") continue
            const due = history[id] ?? Math.max(backgroundSince + 10 * 60_000, Date.parse(r.updated_at ?? r.occurred_at) + offset + 10 * 60_000)
            nextHistory[id] = due
            if (due > now) wanted.set(id, { due, key, kind: "empty", title: "Начнём тренировку?",
                body: "Она открыта, подходов пока нет.", categoryIdentifier: "mentor_restart_close_empty" })
        }
    }
    if (state !== latest) return
    for (const n of pending) if (!wanted.has(n.identifier)) await Notifications.cancelScheduledNotificationAsync(n.identifier)
    for (const [identifier, n] of wanted) {
        if (existing.has(identifier)) continue
        await Notifications.scheduleNotificationAsync({ identifier, trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: new Date(n.due), channelId: "default" },
            content: { title: n.title, body: n.body, categoryIdentifier: n.categoryIdentifier, sound: "default",
                data: { type: "mentor_notice", key: n.key, kind: n.kind, profile: profile!.id } } })
    }
    const serialized = JSON.stringify(nextHistory)
    if (serialized !== (raw ?? "{}")) {
        if (Object.keys(nextHistory).length) await SecureStore.setItemAsync(emptyHistoryKey, serialized)
        else await SecureStore.deleteItemAsync(emptyHistoryKey)
    }
}
