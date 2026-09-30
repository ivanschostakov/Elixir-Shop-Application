// Isolated browser fixture. This file is never imported by application routes.
import React, { useState } from "react"
import { createRoot } from "react-dom/client"
import { Alert, ScrollView, Text, View } from "react-native"
import { MentorWorkspace, MentorNavigation } from "@/screens/chat/mentor"
import { lightColors } from "@/theme/colors"
import { calendarDate } from "@/screens/chat/companion-timezones"

const today = new Date()
const iso = days => new Date(today.getTime() - days * 86400000).toISOString()
const date = calendarDate()
const meal = { id: 1, version: 1, kind: "meal", occurred_at: iso(0), data: { kind: "meal", occurred_at: iso(0), name: "Тестовый обед", nutrition: { kcal: "450", protein: "25", fat: "15", carbs: "50" }, favorite: false } }
const weights = [83, 82.7, 82.9].map((weight, index) => ({ id: 10 + index, version: 1, kind: "weight", occurred_at: iso(6 - index * 2), data: { kind: "weight", occurred_at: iso(6 - index * 2), weight_kg: String(weight) } }))
const photoMessages = [{ id: 301, sender: "user", text: "Фото прогресса", created_at: iso(0), attachments: [{ id: 301, message_id: 301, type: "image", is_private: true, download_path: "/api/v1/users/me/ai-chat/attachments/301", filename: "fixture.jpg" }] }]
const plan = { name: "Тестовый план", start_date: date, end_date: null, days: [{ key: "upper", name: "Верх тела", weekdays: [(today.getDay() + 6) % 7], exercises: [{ key: "press", name: "Жим", sets: 2, target_reps: 8, target_weight_kg: "20" }, { key: "row", name: "Тяга", sets: 1, target_reps: 10, target_weight_kg: "15" }] }] }
export const summary = { nutrition: { kcal: "9800", protein: "700", fat: "300", carbs: "1000" }, meals_logged: 24, days_with_meals: 7, weight_measurements: 3, weight_change_kg: "-0.1", events: { done: 2, pending: 1, skipped: 0 }, coverage_note: "Итоги только по сохранённым данным.", workouts: { sessions: 1, completed: 0, in_progress: 1, completed_sets: 0, reps: 0, volume_kg: "0", duration_seconds: 0 }, measurements: { count: 0, latest: {}, change: {} }, wellbeing: { entries: 0, average_score: null } }
export const store = { entries: [meal, ...weights], events: [], actions: [], state: { available: true, consent_required: false, consent_version: "test", dialogue_protocol: 2, profile: { id: 1, version: 1, enabled: true, data: { goal: "weight_gain", target_weight_kg: "88" }, settings: { timezone: "UTC" } }, entries: [meal, ...weights], today: { ...summary, meals_logged: 1 }, mentor: { latest_weight: weights[2], workout_plan: plan, today: { date, nutrition: { consumed: meal.data.nutrition, target: { kcal: "2200", protein: "130", fat: "70", carbs: "220" }, remaining: { kcal: "1750", protein: "105", fat: "55", carbs: "170" } }, tasks: [{ id: "workout:upper", kind: "workout", label: "Верх тела", status: "pending" }], course: { scheduled: 0, done: 0, pending: 0, skipped: 0 }, workouts: { scheduled: 1, completed: 0, in_progress: 0 } }, week: { from_date: date, to_date: date, summary } } } }
export const useTheme = () => ({ palette: lightColors })
export const requestKey = () => `fixture-${Date.now()}-${Math.random()}`
export const getCompanionEntries = async () => ({ entries: structuredClone(store.entries) })
export const getCompanionProgressPhotos = async () => ({ entries: store.entries.filter(entry => entry.kind === "progress_photo"), limit: 200, may_have_more: false })
export const getCompanionFavoriteMeals = async () => ({ entries: store.entries.filter(entry => entry.kind === "meal" && entry.data.favorite), limit: 200, may_have_more: false })
export const getCompanionEvents = async () => ({ events: store.events })
export const getCompanionSummary = async () => structuredClone(summary)
export const companionDialogue = async (...args) => store.actions.push({ report: args })
export const useRouter = () => ({ push: route => store.actions.push({ route }) })

Alert.alert = (_title, _text, buttons) => { window.__confirmation = buttons; if (window.confirm(_text)) buttons[buttons.length - 1].onPress?.() }
function App() {
    const [state, setState] = useState(structuredClone(store.state))
    const [mentorPage, setMentorPage] = useState("today")
    const [error, setError] = useState("")
    const [busy, setBusy] = useState(false)
    const controller = { state, enabled: true, clock: `UTC|0|${date}`, mentorPage, setMentorPage, busy, error, setError,
        setEditor: value => store.actions.push({ editor: value }),
        refresh: async () => state,
        attempt: async fn => { try { await fn() } catch (e) { setError(e.message) } },
        perform: async action => {
            store.actions.push(action); setBusy(true)
            if (action.kind === "entry") {
                const existing = store.entries.find(entry => entry.id === action.resource_id)
                if (existing && existing.version !== action.expected_version) throw new Error("Version conflict")
                const entry = { id: existing?.id ?? Math.max(...store.entries.map(entry => entry.id)) + 1, version: (existing?.version ?? 0) + 1, kind: action.entry.kind, occurred_at: action.entry.occurred_at, data: action.entry }
                store.entries = [...store.entries.filter(value => value.id !== entry.id), entry]
            }
            const next = { ...state, entries: structuredClone(store.entries) }
            if (action.kind === "workout_plan") next.mentor = { ...next.mentor, workout_plan: action.workout_plan }
            store.state = next; setState(next); setBusy(false); return next
        },
    }
    window.__mentor = { store, setMentorPage, setState }
    return <View style={{ height: "100vh", backgroundColor: "#EFF5F1" }}><ScrollView style={{ flex: 1 }}><MentorWorkspace controller={controller} onPrompt={async text => store.actions.push({ prompt: text })} onCompose={(mode, text) => store.actions.push({ compose: mode, text })} photoMessages={photoMessages} renderPhotoAttachments={attachments => attachments.map(attachment => <View key={attachment.id} style={{ height: 90, backgroundColor: "#e5e7eb" }}><Text>Private test attachment {attachment.id}</Text></View>)} /></ScrollView><View testID="fixture-navigation" style={{ backgroundColor: "white", padding: 8, flexShrink: 0 }}><MentorNavigation controller={controller} /></View></View>
}
createRoot(document.getElementById("root")).render(<App />)
