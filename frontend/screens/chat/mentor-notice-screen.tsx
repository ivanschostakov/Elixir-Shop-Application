import { useCallback, useEffect, useRef, useState } from "react"
import { ActivityIndicator, ScrollView, Text, View } from "react-native"
import { useLocalSearchParams, useRouter } from "expo-router"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useCompanion } from "@/screens/chat/companion"
import { shiftCalendarDay } from "@/screens/chat/companion-timezones"
import { MentorGoalCelebration } from "@/screens/chat/mentor-goal-celebration"
import { MentorHomeHeader } from "@/screens/chat/mentor-home"
import { mentorHomeData } from "@/screens/chat/mentor-home-data"
import { MentorFoodSuggestions } from "@/screens/chat/mentor-food-suggestions"
import { MentorFoodEditor } from "@/screens/chat/mentor-food"
import { MentorWellbeingEditor } from "@/screens/chat/mentor-wellbeing-form"
import { trainingRepLabel } from "@/screens/chat/mentor-training-data"
import { MentorTrainingPlan } from "@/screens/chat/mentor-training-plan"
import { MentorTrainingSession } from "@/screens/chat/mentor-training-session"
import { TrainingAction, TrainingField } from "@/screens/chat/mentor-training-ui"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { actionLabels } from "@/services/notifications/mentor-push"
import { getWorkoutLibrary } from "@/services/api/companion-workouts"
import { openMentorNotice, type NoticeOptions, type CompanionEntry, type NoticeResult } from "@/services/api/companion"
import { getErrorMessage } from "@/utils/errors"

export default function MentorNoticeRoute() {
    const { profile, notice, action } = useLocalSearchParams<{ profile: string; notice: string; action?: string }>()
    return <NoticeScreen key={JSON.stringify([profile, notice, action])} profile={Number(profile)} notice={notice} initialAction={action} />
}

function NoticeScreen({ profile, notice, initialAction }: { profile: number; notice: string; initialAction?: string }) {
    const c = useCompanion(), current = useRef(c); current.current = c
    const router = useRouter(), insets = useSafeAreaInsets(), colors = useMentorPalette()
    const [result, setResult] = useState<NoticeResult>({}), [busy, setBusy] = useState(false), [error, setError] = useState("")
    const [amount, setAmount] = useState("250"), [session, setSession] = useState<CompanionEntry | null>(null)
    const [duration, setDuration] = useState("")
    const locked = useRef(false), active = useRef(true), initial = useRef(false)
    const close = () => { if (router.canGoBack()) router.back(); else router.replace("/discover") }
    const saved = async () => { await current.current.refresh(); if (active.current) setResult({ screen: "done", message: "Запись сохранена" }) }
    const run = useCallback(async (action?: string, options?: NoticeOptions) => {
        if (locked.current) return
        locked.current = true; setBusy(true); setError("")
        try {
            if (action === "later" && !options?.minutes) {
                setResult({ screen: "snooze" }); return
            }
            const next = await openMentorNotice(profile, notice, action, options)
            if (action || next.screen) await current.current.refresh()
            if (next.screen === "session") {
                const day = mentorHomeData(current.current.state, current.current.clock).date
                const entries = (await getWorkoutLibrary(shiftCalendarDay(day, -1), shiftCalendarDay(day, 1))).entries
                const entry = entries.find(e => e.id === next.entry_id)
                if (!entry) throw new Error(mt("Тренировка больше недоступна"))
                if (active.current) setSession(entry)
            }
            if (active.current) setResult(next)
        } catch (e) { if (active.current) setError(getErrorMessage(e)) }
        finally { locked.current = false; if (active.current) setBusy(false) }
    }, [profile, notice])
    useEffect(() => {
        active.current = true
        return () => { active.current = false }
    }, [])
    useEffect(() => {
        if (!c.initialized || initial.current) return
        initial.current = true
        void run(initialAction || undefined)
    }, [c.initialized, initialAction, run])
    const start = () => {
        const minutes = Number(duration)
        if (result.retrospective && (!Number.isInteger(minutes) || minutes < 1 || minutes > 1440)) {
            setError(mt("Укажите длительность от 1 до 1440 минут"))
            return
        }
        void run(result.retrospective ? "log_workout" : "plan", { start_workout: true, duration_minutes: result.retrospective ? minutes : undefined })
    }
    const screen = result.screen
    const actionButton = (id: string, label: string, press: () => void, secondary = false) => <TrainingAction key={id} label={mt(label)} disabled={busy} onPress={press} secondary={secondary} />
    const body = () => {
        if (screen === "session" && session) return <MentorTrainingSession controller={c} entry={session} onUpdated={setSession} onClose={close} />
        if (screen === "new_plan") return <MentorTrainingPlan controller={c} mode="generate" today={mentorHomeData(c.state, c.clock).date} onClose={close} onSaved={close} />
        if (screen === "checkin") return <MentorWellbeingEditor controller={{ ...c, editor: { page: "wellbeing", entry: c.state?.entries?.find(e => e.id === result.wellbeing_id) } }} onClose={close} />
        if (screen === "recipes") return <View style={{ flex: 1, paddingTop: insets.top }}>
            <MentorFoodSuggestions controller={c} shown onClose={close} gaps={result.gaps} meal={result.meal} />
        </View>
        if (screen === "meal" || screen === "photo") {
            const editor = { page: "meal" as const, entry: result.original ?? undefined, estimate: result.estimate, estimateRequest: result.request, mealType: result.meal, mealKey: result.meal_key }
            return <MentorFoodEditor controller={{ ...c, editor }} shown onClose={close} onSaved={saved} />
        }
        return <View style={{ flex: 1, paddingTop: insets.top }}>
            <MentorHomeHeader title={mt("Наставник")} onBack={close} />
            <ScrollView contentContainerStyle={{ padding: 24, gap: 16, paddingBottom: insets.bottom + 24 }}>
                {busy && <ActivityIndicator color={colors.green} />}
                {error ? <><Text accessibilityRole="alert" style={{ color: colors.text }}>{error}</Text>{actionButton("retry", "Обновить", () => void run())}</> : null}
                {result.title || result.message ? <Text accessibilityRole="header" style={{ color: colors.text, fontSize: 24, fontWeight: "700" }}>{result.title || result.message}</Text> : null}
                {result.body && <Text style={{ color: colors.muted, fontSize: 17 }}>{result.body}</Text>}
                {result.actions?.map((id, i) => actionButton(id, actionLabels[id], () => void run(id), i > 0))}
                {screen === "rating" && [1, 2, 3, 4, 5].map(value => actionButton(String(value), String(value), () => void run("checkin", { score: value })))}
                {screen === "snooze" && <><Text style={{ color: colors.text }}>{mt("Через сколько напомнить?")}</Text>{[15, 30, 60].map(minutes => actionButton(String(minutes), mt("{0} мин", [minutes]), () => void run("later", { minutes })))}</>}
                {screen === "water_amount" && <><TrainingField label={mt("Объём воды, мл")} value={amount} onChange={setAmount} numeric labeled />
                    {actionButton("save", "Записать", () => void run("other_water", { ml: Number(amount) }))}</>}
                {screen === "plan" && result.block && <><Text style={{ color: colors.text, fontSize: 25 }}>{result.block.name}</Text>
                    {result.block.exercises.map(e => <Text key={e.key} style={{ color: colors.text }}>{e.name} · {trainingRepLabel(e)}</Text>)}
                    {result.retrospective && <TrainingField label={mt("Длительность, минут")} value={duration} onChange={setDuration} numeric labeled />}
                    {actionButton("start", result.retrospective ? "Записать подходы" : "Открыть тренировку", () => void start())}</>}
                {screen === "suggestion" && <>
                    <Text style={{ color: colors.text, fontSize: 18 }}>{Object.entries(result.gaps ?? {}).map(([k, v]) => mt(({ protein: "Белки", kcal: "Калории", fat: "Жиры", carbs: "Углеводы" } as Record<string,string>)[k]) + " · " + v + " " + mt(k === "kcal" ? "ккал" : "г")).join("  ")}</Text>
                    {!!result.water_gap && <Text style={{ color: colors.muted }}>{mt("Вода")} · {result.water_gap} {mt("мл")}</Text>}
                    {result.dish ? <><Text style={{ color: colors.text, fontSize: 22 }}>{result.dish.data.name}{result.dish.data.portion_g ? " · " + result.dish.data.portion_g + " " + mt("г") : ""}</Text>
                        <Text style={{ color: colors.muted }}>{result.dish.data.nutrition?.kcal} {mt("ккал")} · {mt("Белки")} {result.dish.data.nutrition?.protein} {mt("г")} · {mt("Жиры")} {result.dish.data.nutrition?.fat} {mt("г")} · {mt("Углеводы")} {result.dish.data.nutrition?.carbs} {mt("г")}</Text>
                        {actionButton("open", "Открыть блюдо", () => setResult({ screen: "meal", meal: result.meal, estimate: { ...result.dish!.data, favorite: false, water_ml: undefined, food_photo_attachment_ids: [] } }))}</>
                    : <Text style={{ color: colors.text }}>{mt("Подходящих блюд в дневнике пока нет.")}</Text>}
                    {actionButton("recipes", "Подобрать рецепт", () => setResult({ ...result, screen: "recipes" }), !!result.dish)}
                </>}
                {screen === "done" && result.wellbeing_id && c.state?.entries?.some(e => e.id === result.wellbeing_id) && actionButton("details", "Дополнить отметку", () => setResult({ ...result, screen: "checkin" }), true)}
                {screen === "done" && actionButton("done", "Готово", close)}
            </ScrollView></View>
    }
    const today = c.state?.mentor?.today
    return <View style={{ flex: 1, backgroundColor: colors.surface }}>{body()}
        {today && c.state?.profile?.id === profile && <MentorGoalCelebration key={profile + today.date} today={today} visible={screen === "done"} top={insets.top} />}</View>
}
