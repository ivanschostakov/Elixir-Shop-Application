// Isolated synthetic native preview. Uses production screens and no real account.
import React, { useRef, useState } from "react"
import { registerRootComponent } from "expo"
import { NativeModules, Text, View } from "react-native"
import { SafeAreaProvider } from "react-native-safe-area-context"
import { MentorOnboarding } from "@/screens/chat/mentor-onboarding"
import { MentorOptionalOnboarding } from "@/screens/chat/mentor-onboarding-optional"
import { MentorNutritionResult } from "@/screens/chat/mentor-nutrition-result"
import { MentorMainScreen } from "@/screens/chat/mentor-main"
import { calendarDate, deviceClockKey } from "@/screens/chat/companion-timezones"
import { mentorFormFromState, mentorOptionalFormFromState } from "@/screens/chat/mentor-onboarding-data"
import { darkColors, lightColors } from "@/theme/colors"
import { translate } from "@/i18n/translations"

export const useTheme = () => {
    const isDark = globalThis.__MENTOR_PREVIEW_DARK__ === true
    return { palette: isDark ? darkColors : lightColors, isDark, themeName: isDark ? "dark" : "light" }
}
export const useLanguage = () => ({ language: "ru", t: key => translate(key, "ru") })
export const requestKey = () => "synthetic-preview-key"
export const syncPushNotifications = async () => "synthetic-notification-token"
const saved = { available: true, consent_required: false, profile: { id: 1, version: 1, data: { goal: "weight_loss", age: 32, sex: "female", height_cm: "170", activity: "moderate", nutrition: { kcal: "1900", protein: "130", fat: "60", carbs: "210" } } }, mentor: { latest_weight: { data: { weight_kg: "78.5" } } } }
const day = calendarDate(), started = new Date(); started.setHours(0, 0, 0, 0)
const elapsed = Date.now() - started.getTime()
const meal = (id, share, name, nutrition) => {
    const occurred_at = new Date(started.getTime() + elapsed * share).toISOString()
    return { id, version: 1, kind: "meal", occurred_at, data: { kind: "meal", name, occurred_at, nutrition } }
}
const entries = [meal(1, 0.3, "Омлет и тост", { kcal: 520, protein: 26, fat: 24, carbs: 50 }), meal(2, 0.7, "Курица с гречкой", { kcal: 720, protein: 70, fat: 24, carbs: 56 })]
const workoutPlan = { name: "Мои тренировки", start_date: day, end_date: null, days: [{ key: "today", name: "Лёгкая тренировка", weekdays: [(new Date().getDay() + 6) % 7], exercises: [{ key: "squats", name: "Приседания", sets: 3, target_reps: 12, target_weight_kg: null }] }] }
let previewState = { ...saved, dialogue_protocol: 2, entries, events: [], profile: { ...saved.profile, enabled: true, data: { ...saved.profile.data, target_weight_kg: 75, onboarding_optional_step: 5, workout_plan: workoutPlan } },
    mentor: { ...saved.mentor, latest_weight: { ...saved.mentor.latest_weight, id: 3, version: 1, kind: "weight", occurred_at: new Date(started.getTime() + elapsed * 0.1).toISOString() }, workout_plan: workoutPlan, today: { date: day, tasks: [{ id: "workout:today", kind: "workout", label: "Лёгкая тренировка", status: "pending", resource_id: null }], nutrition: { consumed: { kcal: 1240, protein: 96, fat: 48, carbs: 106 }, target: saved.profile.data.nutrition } } } }
export const getCompanionEntries = async () => ({ entries: previewState.entries })
export const getCompanionEvents = async () => ({ events: [] })
export const getCompanionFavoriteMeals = async () => ({ entries: [], may_have_more: false })
export const getCompanionSummary = async () => ({ nutrition: previewState.mentor.today.nutrition.consumed })
export const getNutritionSuggestion = async () => ({ available: false })
export const estimateCompanionFood = async text => {
    await new Promise(resolve => setTimeout(resolve, 700))
    return { entry: { kind: "meal", name: "Рис с курицей", note: text, occurred_at: new Date().toISOString(), estimated: true, assumptions: "Оценка для одной средней порции", nutrition: { kcal: 450, protein: 32, fat: 12, carbs: 54 } }, message: "Расчёт готов" }
}
export const transcribeMyAiChatVoice = async () => ({ text: "Рис с курицей, одна тарелка" })

function Preview() {
    const source = NativeModules.SourceCode?.getConstants?.().scriptURL ?? ""
    const [screen, setScreen] = useState(globalThis.__MENTOR_PREVIEW_SCREEN__ ?? new URL(source || "http://127.0.0.1").searchParams.get("previewScreen") ?? "required")
    const [homeState, setHomeState] = useState(() => screen === "home-empty" ? { ...previewState, entries: [], mentor: { ...previewState.mentor, today: { ...previewState.mentor.today, tasks: [], nutrition: { target: saved.profile.data.nutrition, consumed: { kcal: 0, protein: 0, fat: 0, carbs: 0 } } } } } : previewState)
    const homeRef = useRef(homeState); homeRef.current = homeState; previewState = homeState
    const [editor, updateEditor] = useState(null)
    const setEditor = value => updateEditor(value?.page === "meal" && !value.entry && globalThis.__MENTOR_PREVIEW_FOOD_TEXT__ ? { ...value, proposal: { entry: { kind: "meal", note: globalThis.__MENTOR_PREVIEW_FOOD_TEXT__ } } } : value)
    const controller = { state: homeState, clock: deviceClockKey(), initialized: true, enabled: true, busy: false, error: "", editor, setEditor, setError() {}, refresh: async () => homeRef.current,
        attempt: async operation => operation(), perform: async action => {
            let next = { ...homeRef.current }
            if (action.entry) {
                const entry = { id: action.resource_id ?? Date.now(), version: 1, kind: action.entry.kind, occurred_at: action.entry.occurred_at, data: action.entry }
                next.entries = [...next.entries.filter(item => item.id !== entry.id), entry]
                const consumed = Object.fromEntries(["kcal", "protein", "fat", "carbs"].map(key => [key, next.entries.filter(item => item.kind === "meal").reduce((sum, item) => sum + Number(item.data.nutrition?.[key] ?? 0), 0)]))
                next.mentor = { ...next.mentor, today: { ...next.mentor.today, nutrition: { ...next.mentor.today.nutrition, consumed } } }
            }
            next.profile = { ...next.profile, version: next.profile.version + 1 }
            homeRef.current = next; setHomeState(next); return next
        } }
    const [form, setForm] = useState({ ...mentorFormFromState(saved), ...(screen === "activity" ? { activity: null } : {}) })
    const [optional, setOptional] = useState(mentorOptionalFormFromState(saved))
    const [step, setStep] = useState(screen === "reminders" ? 5 : screen === "experience" ? 3 : screen === "conditions" ? 4 : 0)
    const close = () => setScreen("home")
    const content = screen === "result" ? <MentorNutritionResult state={saved} onContinue={() => { setScreen("optional"); setStep(0) }} onDecline={close} onBack={() => setScreen("required")} onClose={close} /> : ["optional", "experience", "conditions", "reminders"].includes(screen) ? <MentorOptionalOnboarding value={optional} onChange={setOptional} step={step} onBack={() => step ? setStep(step - 1) : setScreen("result")} onClose={close} onNext={() => step === 5 ? close() : setStep(step + 1)} saving={false} error="" /> : ["home", "home-empty"].includes(screen) ? <MentorMainScreen controller={controller} onClose={() => setScreen("required")} onAsk={() => setScreen("ask")} onContinue={() => { setScreen("optional"); setStep(0) }} /> : screen === "ask" ? <View><Text>Спросить наставника</Text></View> : undefined
    return <SafeAreaProvider><View style={{ flex: 1, backgroundColor: "white" }}><MentorOnboarding visible value={form} onChange={setForm} onClose={close} onSave={async () => setScreen("result")} saving={false} error="">{content}</MentorOnboarding></View></SafeAreaProvider>
}
registerRootComponent(Preview)
