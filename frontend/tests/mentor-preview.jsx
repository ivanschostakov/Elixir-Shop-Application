// Isolated synthetic browser fixture. Never imported by application routes.
// Reference values demonstrate the requested layout; these are not account data.
import React, { createContext, useContext, useEffect, useRef, useState } from "react"
import { createRoot } from "react-dom/client"
import { Alert, Pressable, ScrollView, Text, useWindowDimensions, View } from "react-native"
import Svg, { Path } from "react-native-svg"
import { MentorWorkspace, MentorNavigation } from "@/screens/chat/mentor"
import { ChatBackdrop } from "@/screens/chat/chat-backdrop"
import { ContentReveal, QuietLoading } from "@/components/ui/quiet-loading"
import { ChatModeSwitcher } from "@/screens/chat/chat-mode-switcher"
import { ChatModePane, ChatModeTransition } from "@/screens/chat/chat-mode-transition"
import { MentorModeToggle } from "@/screens/chat/mentor-mode-toggle"
import { SendActionButton } from "@/screens/chat/chat-screen.core-components"
import { createChatScreenStyles } from "@/screens/chat/chat-screen.styles"
import { ChatKeyboardLayout } from "@/screens/chat/chat-keyboard-layout"
import { ChatComposerInput } from "@/screens/chat/chat-composer-input"
import { ChatFormFocusProvider } from "@/screens/chat/chat-form-focus"
import { useChatScroll } from "@/hooks/chat/use-chat-scroll"
import { useMentorMode } from "@/hooks/chat/use-mentor-mode"
import AttachmentIcon from "@/assets/icons/chat/attachment-svgrepo-com.svg"
import { lightColors } from "@/theme/colors"
import { calendarDate, companionCalendarDay, deviceClockKey } from "@/screens/chat/companion-timezones"
import { setTranslationLanguage, translate } from "@/i18n/translations"

const today = new Date()
const iso = days => new Date(today.getTime() - days * 86400000 - 3600000).toISOString()
const date = calendarDate()
const meal = { id: 1, version: 1, kind: "meal", occurred_at: iso(0), data: { kind: "meal", occurred_at: iso(0), name: "Тестовый обед", nutrition: { kcal: "450", protein: "25", fat: "15", carbs: "50" }, favorite: false } }
const weights = [92, 91.8, 91.7, 91.5, 91.6, 91.4, 91.3].map((weight, index) => ({ id: 10 + index, version: 1, kind: "weight", occurred_at: iso(6 - index), data: { kind: "weight", occurred_at: iso(6 - index), weight_kg: String(weight) } }))
const photoMessages = [{ id: 301, sender: "user", text: "Фото прогресса", created_at: iso(0), attachments: [{ id: 301, message_id: 301, type: "image", is_private: true, download_path: "/api/v1/users/me/ai-chat/attachments/301", filename: "fixture.jpg" }] }]
const historyMessages = Array.from({ length: 24 }, (_, index) => ({
    id: `history-${index}`,
    sender: index % 2 ? "ai" : "user",
    text: index === 22 ? "Фото еды. Уточни состав и размер порции перед сохранением." : `Сообщение ${index + 1}. ${"Длинная история остаётся доступной при открытой клавиатуре. ".repeat(3)}`,
    photo: index === 22,
}))
const plan = { name: "Тестовый план", start_date: date, end_date: null, days: [{ key: "upper", name: "Верх тела", weekdays: [(today.getDay() + 6) % 7], exercises: [{ key: "press", name: "Жим", sets: 2, target_reps: 8, target_weight_kg: "20" }, { key: "row", name: "Тяга", sets: 1, target_reps: 10, target_weight_kg: "15" }] }] }
export const summary = { nutrition: { kcal: "9800", protein: "700", fat: "300", carbs: "1000" }, meals_logged: 24, days_with_meals: 7, weight_measurements: 7, weight_change_kg: "-0.7", events: { done: 2, pending: 3, skipped: 0 }, coverage_note: "Итоги только по сохранённым данным.", workouts: { sessions: 1, completed: 0, in_progress: 1, completed_sets: 0, reps: 0, volume_kg: "0", duration_seconds: 0 }, measurements: { count: 0, latest: {}, change: {} }, wellbeing: { entries: 0, average_score: null } }
export const store = {
    entries: [meal, ...weights], events: [], actions: [], summary,
    state: {
        available: true, consent_required: false, consent_version: "test", dialogue_protocol: 2,
        profile: { id: 1, version: 1, enabled: true, data: { goal: "weight_loss", target_weight_kg: "85" }, settings: { timezone: deviceClockKey().split("|")[0] } },
        entries: [meal, ...weights], today: { ...summary, meals_logged: 3 },
        mentor: {
            latest_weight: weights[0], workout_plan: plan,
            today: {
                date,
                nutrition: { consumed: { kcal: "1240", protein: "82", fat: "42", carbs: "130" }, target: { kcal: "1900", protein: "130", fat: "65", carbs: "200" }, remaining: { kcal: "660", protein: "48", fat: "23", carbs: "70" } },
                tasks: [
                    { id: "course:morning", kind: "course", label: "Утреннее напоминание", status: "done", resource_id: 1, version: 1, scheduled_at: `${date}T08:00:00Z`, plan_day_key: null },
                    { id: "workout:mobility", kind: "workout", label: "Утренняя разминка", status: "done", resource_id: 2, version: 1, scheduled_at: `${date}T09:00:00Z`, plan_day_key: "mobility" },
                    { id: "workout:upper", kind: "workout", label: "Верх тела", status: "pending", scheduled_at: `${date}T18:00:00Z`, resource_id: null, version: null, plan_day_key: "upper" },
                    { id: "course:evening", kind: "course", label: "Напоминание", status: "pending", scheduled_at: `${date}T20:00:00Z`, resource_id: 3, version: 1, plan_day_key: null },
                    { id: "course:night", kind: "course", label: "Вечернее напоминание", status: "pending", resource_id: 4, version: 1, scheduled_at: `${date}T21:00:00Z`, plan_day_key: null },
                ],
                course: { scheduled: 1, done: 0, pending: 1, skipped: 0 }, workouts: { scheduled: 1, completed: 0, in_progress: 0 },
            },
            week: { from_date: calendarDate(-6), to_date: date, summary },
        },
    },
}
export const useTheme = () => ({ palette: lightColors, themeName: "light" })
const PreviewLanguageContext = createContext({ language: "ru", t: key => translate(key, "ru") })
export const useLanguage = () => useContext(PreviewLanguageContext)
export const requestKey = () => `fixture-${Date.now()}-${Math.random()}`
export const getCompanionEntries = async (from, to, kind) => { await waitForData(); return { entries: structuredClone(store.entries.filter(entry => {
    const day = companionCalendarDay(entry.occurred_at, deviceClockKey())
    return (!kind || entry.kind === kind) && (!from || day >= from) && (!to || day < to)
})) } }
export const getCompanionProgressPhotos = async () => ({ entries: store.entries.filter(entry => entry.kind === "progress_photo"), limit: 200, may_have_more: false })
export const getCompanionFavoriteMeals = async () => ({ entries: store.entries.filter(entry => entry.kind === "meal" && entry.data.favorite), limit: 200, may_have_more: false })
export const getCompanionEvents = async () => ({ events: store.events })
const waitForData = (kind = "entries") => new Promise(resolve => setTimeout(resolve, Number(new URLSearchParams(location.search).get(kind === "summary" ? "summaryDelay" : "dataDelay")) || Number(new URLSearchParams(location.search).get("dataDelay")) || 0))
export const getCompanionSummary = async () => { await waitForData("summary"); return structuredClone(store.summary) }
export const companionDialogue = async (...args) => store.actions.push({ report: args })
export const useRouter = () => ({ push: route => store.actions.push({ route }) })

Alert.alert = (_title, _text, buttons) => { window.__confirmation = buttons; if (window.confirm(_text)) buttons[buttons.length - 1].onPress?.() }
function App() {
    const [language, setLanguage] = useState(new URLSearchParams(location.search).get("lang") || "ru")
    setTranslationLanguage(language)
    const { height } = useWindowDimensions()
    const initialHeight = useRef(height)
    // Browser-only constraint simulation; UIKit avoidance is verified separately.
    const keyboardVisible = height < initialHeight.current - 140
    const phonePreview = new URLSearchParams(location.search).get("device") === "phone"
    const styles = createChatScreenStyles(lightColors)
    const [initialReady, setInitialReady] = useState(!new URLSearchParams(location.search).has("initialDelay"))
    useEffect(() => { const timer = setTimeout(() => setInitialReady(true), Number(new URLSearchParams(location.search).get("initialDelay")) || 0); return () => clearTimeout(timer) }, [])
    const [state, setState] = useState(structuredClone(store.state))
    const [mentorPage, setMentorPage] = useState(new URLSearchParams(location.search).get("page") || "today")
    const [chatMode, setChatMode] = useState("ai")
    const [error, setError] = useState("")
    const [busy, setBusy] = useState(false)
    const [draft, setDraft] = useState("")
    const [messages, setMessages] = useState([])
    const [recording, setRecording] = useState(false)
    const scrollRef = useRef(null)
    const mentorMode = useMentorMode(async () => true)
    const mentorVisible = mentorMode.shown && !!mentorPage
    const chatScroll = useChatScroll(scrollRef, mentorVisible ? mentorPage : null)
    const toggleMentor = () => {
        mentorMode.setShown(!mentorMode.shown)
        if (mentorMode.shown) chatScroll.followLatest()
        else setMentorPage(current => current ?? "today")
    }
    const controller = { state, enabled: true, clock: deviceClockKey(), mentorPage, setMentorPage, busy, error, setError,
        setEditor: value => store.actions.push({ editor: value }),
        refresh: async () => state,
        attempt: async fn => { try { await fn() } catch (e) { setError(e.message) } },
        perform: async action => {
            store.actions.push(action); setBusy(true)
            try {
                if (action.kind === "entry") {
                    const existing = store.entries.find(entry => entry.id === action.resource_id)
                    if (existing && existing.version !== action.expected_version) throw new Error("Version conflict")
                    const entry = { id: existing?.id ?? Math.max(...store.entries.map(entry => entry.id)) + 1, version: (existing?.version ?? 0) + 1, kind: action.entry.kind, occurred_at: action.entry.occurred_at, data: action.entry }
                    store.entries = [...store.entries.filter(value => value.id !== entry.id), entry]
                }
                const next = { ...state, entries: structuredClone(store.entries) }
                if (action.kind === "workout_plan") next.mentor = { ...next.mentor, workout_plan: action.workout_plan }
                store.state = next; setState(next); return next
            } finally { setBusy(false) }
        },
    }
    const compose = (mode, text) => { store.actions.push({ compose: mode, text }); setDraft(text); if (mode === "voice") setRecording(true) }
    const send = async () => {
        if (!draft.trim()) { setRecording(value => !value); return }
        const companionEnabled = await mentorMode.resolveEnabled()
        chatScroll.followLatest()
        store.actions.push({ message: draft, companionEnabled }); setMessages(value => [...value, { id: `sent-${value.length}`, sender: "user", text: draft }]); setDraft(""); setMentorPage(null)
    }
    window.__mentor = { store, setMentorPage, setState, setLanguage, language, initialReady, shown: mentorMode.shown, mentorPage, chatMode,
        loadHistory: () => setMessages(historyMessages),
        seedHistory: () => { setMentorPage(null); setMessages(historyMessages) },
        appendMessage: () => setMessages(value => [...value, { id: `incoming-${value.length}`, sender: "ai", text: "Новый ответ наставника: история не должна прыгать вниз во время чтения." }]),
    }
    return <PreviewLanguageContext.Provider value={{ language, t: key => translate(key, language) }}><View style={[styles.container, { height: "100vh", minHeight: 0 }, phonePreview ? { width: 390, maxWidth: "100%", alignSelf: "center" } : null]}>
        <ChatBackdrop />
        <ChatKeyboardLayout>
            <View testID="fixture-header" style={[styles.fixedHeader, styles.mentorHeader, { paddingTop: 8 }]}>
                <View style={styles.topBarRow}>
                    <Pressable accessibilityRole="button" accessibilityLabel="Назад" onPress={() => { setChatMode("ai"); setMentorPage("today") }} style={[styles.topBackButton, styles.mentorBackButton]}><Svg fill="none" height={20} viewBox="0 0 24 24" width={20}><Path d="M15.5 5.5 9 12l6.5 6.5" stroke="#12161A" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} /></Svg></Pressable>
                    <ChatModeSwitcher mentorStyle mode={chatMode} onChange={setChatMode} unreadCount={100} />
                </View>
            </View>
        <ChatModeTransition mode={chatMode}>
        <ChatModePane mode="ai" active={chatMode === "ai"}>
        <View style={styles.content}>
            <View style={styles.chatBody}>
                <QuietLoading loading={!initialReady} />
                <ContentReveal ready={initialReady} style={{ flex: 1, minHeight: 0 }}>
                <ScrollView ref={scrollRef} testID="fixture-scroll" keyboardShouldPersistTaps="handled" onScroll={chatScroll.onScroll} onScrollBeginDrag={chatScroll.onScrollBeginDrag} onContentSizeChange={chatScroll.onContentSizeChange} onLayout={chatScroll.onLayout} scrollEventThrottle={16} style={styles.messagesScroll} contentContainerStyle={[styles.messagesContent, mentorVisible ? styles.mentorMessagesContent : null, { paddingTop: mentorVisible && mentorPage === "today" ? Math.max(20, Math.min(76, (height - 660) * .45)) : 12, paddingBottom: 8 }]}>
                    {initialReady ? <>
                        {mentorVisible ? <ChatFormFocusProvider value={chatScroll.onFieldFocus}><MentorWorkspace controller={controller} displayName="Тимур" onPrompt={async text => store.actions.push({ prompt: text })} onCompose={compose} photoMessages={photoMessages} renderPhotoAttachments={attachments => attachments.map(attachment => <View key={attachment.id} style={{ height: 90, backgroundColor: "#e5e7eb" }}><Text>Private test attachment {attachment.id}</Text></View>)} /></ChatFormFocusProvider> : null}
                        {!mentorVisible ? <View style={styles.messageList}>{messages.map(message => <View key={message.id} testID={`fixture-message-${message.id}`} style={[styles.messageBubble, message.sender === "user" ? styles.userMessageBubble : styles.aiMessageBubble]}>
                            {message.photo ? <View testID="fixture-large-photo" accessibilityLabel="Синтетическое фото еды" style={{ height: 430, width: 245, maxWidth: "100%", borderRadius: 14, backgroundColor: "#DACBAE", alignItems: "center", justifyContent: "center" }}><Text>Фото еды · тестовый пример</Text></View> : null}
                            <Text>{message.text}</Text>
                        </View>)}</View> : null}
                    </> : null}
                </ScrollView>
                </ContentReveal>
                <View testID="fixture-composer" style={[styles.composerDock, styles.mentorComposerDock, styles.composerDockInFlow, { paddingBottom: 8 }]}>
                    {<View style={styles.composerShortcuts}>
                        <MentorModeToggle shown={mentorMode.shown} onToggle={toggleMentor} />
                        {mentorMode.shown && !keyboardVisible ? <View testID="fixture-navigation" style={styles.mentorShortcutPanel}><MentorNavigation controller={controller} /></View> : null}
                    </View>}
                    {recording ? <View style={styles.voiceStatusPill}><View style={styles.voiceStatusDot} /><Text style={styles.voiceStatusText}>Тестовая запись голоса</Text></View> : null}
                    <View style={styles.composerRow}>
                        <Pressable accessibilityRole="button" accessibilityLabel="Прикрепить файл" style={styles.circleButton} onPress={() => store.actions.push({ attachment: true })}><AttachmentIcon color="#12161A" height={28} width={28} /></Pressable>
                        <View style={styles.composerInputWrap}><ChatComposerInput accessibilityLabel="Сообщение наставнику" placeholder="Напишите сообщение" placeholderTextColor="#8B9092" style={styles.composerInput} value={draft} onChangeText={setDraft} /></View>
                        <SendActionButton disabled={false} isDark={false} isActive={!!draft.trim()} onPress={send} recording={recording} sending={false} transcribing={false} />
                    </View>
                </View>
            </View>
        </View>
        </ChatModePane>
        <ChatModePane mode="community" active={chatMode === "community"}><View style={{ padding: 24, borderRadius: 24, backgroundColor: "white" }}><Text>Наша группа · тестовая страница</Text></View></ChatModePane>
        <ChatModePane mode="support" active={chatMode === "support"}><View style={{ padding: 24, borderRadius: 24, backgroundColor: "white" }}><Text>Поддержка · тестовая страница</Text></View></ChatModePane>
        </ChatModeTransition>
        </ChatKeyboardLayout>
    </View></PreviewLanguageContext.Provider>
}
createRoot(document.getElementById("root")).render(<App />)
