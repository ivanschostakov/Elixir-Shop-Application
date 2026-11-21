// Isolated synthetic native preview. Uses production screens and no real account.
import React, { useRef, useState } from "react"
import { registerRootComponent } from "expo"
import { NativeModules, Pressable, Text, View } from "react-native"
import { GestureHandlerRootView } from "react-native-gesture-handler"
import { NavigationContext } from "@react-navigation/native"
import { KeyboardProvider } from "react-native-keyboard-controller"
import { MentorChatScreen } from "@/screens/chat/chat-screen"
import { SafeAreaProvider } from "react-native-safe-area-context"
import StickyFooter from "@/components/footer/sticky-footer"
import { MentorOnboarding } from "@/screens/chat/mentor-onboarding"
import { MentorOptionalOnboarding } from "@/screens/chat/mentor-onboarding-optional"
import { MentorNutritionResult } from "@/screens/chat/mentor-nutrition-result"
import { MentorMainScreen } from "@/screens/chat/mentor-main"
import { MentorShortcut } from "@/screens/chat/mentor-shortcut"
import { calendarDate, deviceClockKey } from "@/screens/chat/companion-timezones"
import { mentorFormFromState, mentorOptionalFormFromState } from "@/screens/chat/mentor-onboarding-data"
import { darkColors, lightColors } from "@/theme/colors"
import { translate } from "@/i18n/translations"

export const useTheme = () => {
    const isDark = globalThis.__MENTOR_PREVIEW_DARK__ === true
    return { palette: isDark ? darkColors : lightColors, accentPalette: isDark ? darkColors : lightColors, isDark, themeName: isDark ? "dark" : "light" }
}
export const useLanguage = () => ({ language: "ru", t: key => translate(key, "ru") })
export const useAuth = () => ({ user: { id: 1 }, isAuthenticated: true })
export const useApplyScreenTemplate = () => {}
export const useAiChatEntryConsent = active => active
export const useBasket = () => ({ basket: null })
export const useBasketMutations = () => ({ addItem: async () => {}, removeItem: async () => {}, updateItemQuantity: async () => {} })
export const trackCustomerEvent = async () => {}
export function useAiChat(_enabled, _protocol, _active, scope) {
    const base = (id, sender, text) => ({ id, chat_id: 1, user_id: 1, sender, text, attachments: [], interactive: null, companion_cards: [], dialogue_cards: [], created_at: new Date().toISOString(), updated_at: new Date().toISOString(), usage: null })
    const [messages, setMessages] = useState(() => [base(101, "user", "Что можно добавить на ужин?"), base(102, "ai", "С учётом вашего дневника осталось 660 ккал. Можно приготовить рыбу с овощами и добавить порцию риса. Напишите, что есть дома, и подберём вариант.")])
    const [sending, setSending] = useState(false)
    return { chat: { chat: { id: 1, scope, messages } }, messages, aiTyping: sending, sending, loading: false, refreshing: false, error: null, refresh: async () => {}, performAction: async () => {}, sendMessage: async text => {
        setMessages(value => [...value, base(Date.now(), "user", text)]); setSending(true)
        await new Promise(resolve => setTimeout(resolve, 700))
        setMessages(value => [...value, base(Date.now(), "ai", "Давайте подберём ужин по вашим предпочтениям. Какие продукты есть под рукой?")]); setSending(false)
    } }
}
const navigation = { isFocused: () => true, addListener: () => () => {} }
export const requestKey = () => `preview-${Date.now()}`
export const syncPushNotifications = async () => "synthetic-notification-token"
const saved = { available: true, consent_required: false, profile: { id: 1, version: 1, data: { goal: "weight_loss", age: 32, sex: "female", height_cm: "170", activity: "moderate", nutrition: { kcal: "1900", protein: "130.5", fat: "60.2", carbs: "210.1" } } }, mentor: { latest_weight: { data: { weight_kg: "78.5" } } } }
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
export const getMealLibrary = async () => ({ entries: previewState.entries.filter(entry => entry.kind === "meal"), habits: { breakfast: { time: "08:30", days: 6 }, lunch: { time: "13:00", days: 5 }, dinner: { time: "19:30", days: 7 } } })
const previewRecipes = [{"name": "Рыба с рисом и овощами", "description": "Белок и овощи, чтобы сбалансированно закрыть остаток дня.", "portion": "1 порция · 350 г", "minutes": 25, "nutrition": {"kcal": 540, "protein": 38, "fat": 16, "carbs": 61}, "ingredients": ["Филе рыбы — 150 г", "Рис — 60 г в сухом виде", "Брокколи — 150 г", "Оливковое масло — 8 г"], "steps": ["Сварите рис в подсоленной воде.", "Рыбу запеките при 180 °C около 15 минут.", "Приготовьте брокколи на пару, добавьте масло и подавайте с рисом и рыбой."], "image_query": "salmon vegetables", "image": {"url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/9/98/02021_0652_%281%29_Kuskus_with_baked_salmon_and_vegetable.jpg/960px-02021_0652_%281%29_Kuskus_with_baked_salmon_and_vegetable.jpg", "source_url": "https://commons.wikimedia.org/wiki/File:02021_0652_(1)_Kuskus_with_baked_salmon_and_vegetable.jpg", "author": "Silar", "license": "CC BY-SA 4.0"}}, {"name": "Омлет с овощами и тостом", "description": "Простой вариант с белком, овощами и цельнозерновым хлебом.", "portion": "1 порция · 300 г", "minutes": 15, "nutrition": {"kcal": 470, "protein": 29, "fat": 22, "carbs": 39}, "ingredients": ["Яйца — 2 шт.", "Помидор — 100 г", "Цельнозерновой хлеб — 60 г"], "steps": ["Нарежьте помидор и прогрейте на сковороде.", "Добавьте взбитые яйца, готовьте под крышкой и подавайте с тостом."], "image_query": "vegetable omelette", "image": {"url": "https://upload.wikimedia.org/wikipedia/commons/3/33/Ejjeh.jpg", "source_url": "https://commons.wikimedia.org/wiki/File:Ejjeh.jpg", "author": "Esoterisme", "license": "CC BY-SA 4.0"}}]
export const askNutritionHelp = async mode => {
    await new Promise(resolve => setTimeout(resolve, 450))
    return { entry: null, message: mode === "product" ? "Греческий йогурт: ориентировочно 74 ккал на 100 г. Белки — 10 г, жиры — 2 г, углеводы — 4 г." : "Варианты к ужину", suggestions: mode === "suggest" ? previewRecipes : [], next_meal: mode === "suggest" ? { meal_type: "dinner", meals_left: 1, remaining: { kcal: 660, protein: 34, fat: 12, carbs: 104 }, budget: { kcal: 660, protein: 34, fat: 12, carbs: 104 } } : null }
}
export const getCompanionEntries = async () => ({ entries: previewState.entries })
export const getCompanionEvents = async () => ({ events: [] })
export const getCompanionFavoriteMeals = async () => ({ entries: [], may_have_more: false })
export const getCompanionSummary = async () => ({ nutrition: previewState.mentor.today.nutrition.consumed })
export const getNutritionSuggestion = async () => ({ available: false })
export const estimateCompanionFood = async text => {
    await new Promise(resolve => setTimeout(resolve, 700))
    return { entry: { kind: "meal", name: "Рис с курицей", note: text, occurred_at: new Date().toISOString(), estimated: true, water_ml: /300/.test(text) ? 300 : null, assumptions: "Оценка для одной средней порции", nutrition: { kcal: 450, protein: 32, fat: 12, carbs: 54 } }, message: "Расчёт готов" }
}
export const transcribeMyAiChatVoice = async () => ({ text: "Рис с курицей, одна тарелка" })

function Preview() {
    const { palette } = useTheme()
    const source = NativeModules.SourceCode?.getConstants?.().scriptURL ?? ""
    const [screen, setScreen] = useState(globalThis.__MENTOR_PREVIEW_SCREEN__ ?? new URL(source || "http://127.0.0.1").searchParams.get("previewScreen") ?? "required")
    const [homeState, setHomeState] = useState(() => screen === "home-empty" ? { ...previewState, entries: [], mentor: { ...previewState.mentor, today: { ...previewState.mentor.today, tasks: [], nutrition: { target: saved.profile.data.nutrition, consumed: { kcal: 0, protein: 0, fat: 0, carbs: 0 } } } } } : previewState)
    const homeRef = useRef(homeState); homeRef.current = homeState; previewState = homeState
    const [editor, updateEditor] = useState(null)
    const [mentorQuestion, setMentorQuestion] = useState(null)
    const setEditor = value => updateEditor(value?.page === "meal" && !value.entry && globalThis.__MENTOR_PREVIEW_FOOD_TEXT__ ? { ...value, proposal: { entry: { kind: "meal", note: globalThis.__MENTOR_PREVIEW_FOOD_TEXT__ } } } : value)
    const controller = { state: homeState, clock: deviceClockKey(), initialized: true, enabled: true, resolveEnabled: async () => true, resolveProtocol: () => 2, busy: false, error: "", editor, setEditor, mentorQuestion, askMentor: text => { updateEditor(null); setMentorQuestion({ id: requestKey(), text }) }, questionHandled: id => setMentorQuestion(current => current?.id === id ? null : current), setError() {}, refresh: async () => homeRef.current,
        attempt: async operation => operation(), perform: async action => {
            let next = { ...homeRef.current, as_of: new Date().toISOString(), received_at: Date.now() }
            if (action.kind === "delete_entry") next.entries = next.entries.filter(entry => entry.id !== action.resource_id)
            if (action.entry) {
                const entry = { id: action.resource_id ?? Date.now(), version: 1, kind: action.entry.kind, occurred_at: action.record_now ? new Date().toISOString() : action.entry.occurred_at, data: action.entry }
                next.entries = [...next.entries.filter(item => item.id !== entry.id), entry]
                const consumed = Object.fromEntries(["kcal", "protein", "fat", "carbs"].map(key => [key, next.entries.filter(item => item.kind === "meal").reduce((sum, item) => sum + Number(item.data.nutrition?.[key] ?? 0), 0)]))
                next.mentor = { ...next.mentor, today: { ...next.mentor.today, nutrition: { ...next.mentor.today.nutrition, consumed } } }
            }
            const consumed = Object.fromEntries(["kcal", "protein", "fat", "carbs"].map(key => [key, next.entries.filter(entry => entry.kind === "meal").reduce((sum, entry) => sum + Number(entry.data.nutrition?.[key] ?? 0), 0)]))
            next.profile = { ...next.profile, version: next.profile.version + 1, settings: { timezone: "UTC", ...(next.profile.settings ?? {}), ...(action.settings ?? {}) } }
            next.mentor = { ...next.mentor, today: { ...next.mentor.today, nutrition: { ...next.mentor.today.nutrition, consumed }, water: { consumed_ml: next.entries.filter(entry => entry.kind === "water" || entry.kind === "meal").reduce((sum, entry) => sum + Number(entry.data.water_ml ?? 0), 0), target_ml: next.profile.settings.water_goal_ml ?? 1600 } } }
            homeRef.current = next; setHomeState(next); return next
        } }
    const [form, setForm] = useState({ ...mentorFormFromState(saved), ...(screen === "activity" ? { activity: null } : {}) })
    const [optional, setOptional] = useState(mentorOptionalFormFromState(saved))
    const [step, setStep] = useState(screen === "reminders" ? 5 : screen === "experience" ? 3 : screen === "conditions" ? 4 : 0)
    const close = () => setScreen("home")
    const content = screen === "shop" ? <View style={{ flex: 1 }}><View style={{ flex: 1 }}><Text style={{ color: palette.text }}>Магазин</Text><Pressable onPress={() => setScreen("home")} style={{ padding: 24 }}><Text style={{ color: palette.primary }}>Открыть наставника</Text></Pressable></View><StickyFooter template={{ footer: "nav", header: "none", mode: "standard" }} pathname="/discover" /></View> : screen === "shortcut" ? <View style={{ flex: 1, justifyContent: "flex-end", padding: 8, gap: 8 }}><MentorShortcut goal="weight_loss" onPress={() => setScreen("home")} /><View style={{ borderWidth: 1, borderColor: "#A3B8AB", borderRadius: 24, padding: 18 }}><Text style={{ color: palette.text }}>Сообщение</Text></View></View> : screen === "result" ? <MentorNutritionResult state={saved} onContinue={() => { setScreen("optional"); setStep(0) }} onDecline={close} onBack={() => setScreen("required")} onClose={close} /> : ["optional", "experience", "conditions", "reminders"].includes(screen) ? <MentorOptionalOnboarding value={optional} onChange={setOptional} step={step} onBack={() => step ? setStep(step - 1) : setScreen("result")} onClose={close} onNext={() => step === 5 ? close() : setStep(step + 1)} saving={false} error="" /> : ["home", "home-empty"].includes(screen) ? <View style={globalThis.__MENTOR_PREVIEW_SIZE__ ?? { flex: 1 }}><MentorMainScreen controller={controller} onClose={() => setScreen("shop")} renderChat={props => <MentorChatScreen {...props} controller={controller} />} onContinue={() => { setScreen("optional"); setStep(0) }} /></View> : screen === "ask" ? <View><Text>Спросить наставника</Text></View> : undefined
    return <GestureHandlerRootView style={{ flex: 1 }}><NavigationContext.Provider value={navigation}><SafeAreaProvider><KeyboardProvider preload={false}><View style={{ flex: 1, backgroundColor: "white" }}><MentorOnboarding visible contentSafeTop={!["home", "home-empty", "shop"].includes(screen)} contentSafeBottom={!["home", "home-empty", "shop"].includes(screen)} value={form} onChange={setForm} onClose={close} onSave={async () => setScreen("result")} saving={false} error="">{content}</MentorOnboarding></View></KeyboardProvider></SafeAreaProvider></NavigationContext.Provider></GestureHandlerRootView>
}
registerRootComponent(Preview)
