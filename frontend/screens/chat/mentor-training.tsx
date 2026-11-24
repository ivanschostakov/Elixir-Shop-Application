import { useEffect, useRef, useState } from "react"
import { Alert, Modal, Pressable, ScrollView, Text, View } from "react-native"
import { AppFormLayout } from "@/components/platform/app-form-layout"
import { mentorDateLabel, mentorNumber, mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import type { useCompanion } from "@/screens/chat/companion"
import { CompanionActionCancelled } from "@/screens/chat/companion-consent"
import { shiftCalendarDay } from "@/screens/chat/companion-timezones"
import { MentorHomeHeader } from "@/screens/chat/mentor-home"
import { mentorHomeData } from "@/screens/chat/mentor-home-data"
import { beginTraining, lastTrainingWeight, mergeTrainingEntries, scheduledTraining, trainingEntryDay, trainingRepLabel, trainingWeek, trainingWeekdays, validateTrainingPlan } from "@/screens/chat/mentor-training-data"
import { MentorTrainingPlan } from "@/screens/chat/mentor-training-plan"
import { MentorTrainingSession } from "@/screens/chat/mentor-training-session"
import { TrainingAction, TrainingFrame, TrainingHeading, TrainingIcon, trainingStyles as styles } from "@/screens/chat/mentor-training-ui"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { requestKey, type CompanionAction, type CompanionEntry } from "@/services/api/companion"
import { getWorkoutLibrary } from "@/services/api/companion-workouts"
import { getErrorMessage } from "@/utils/errors"

const showAlert = (message: string) => Alert.alert(mt("Тренировки"), message)

type Controller = ReturnType<typeof useCompanion>
export function MentorTrainingScreen({ controller: c, active, onClose, onSettings }: { controller: Controller; active: boolean; onClose: () => void; onSettings: () => void }) {
    useLanguage()
    const colors = useMentorPalette(), today = mentorHomeData(c.state, c.clock).date
    const [selected, setSelected] = useState(today), [block, setBlock] = useState(0)
    const [library, setLibrary] = useState<CompanionEntry[]>([]), [loaded, setLoaded] = useState(false), [loadError, setLoadError] = useState("")
    const [refresh, setRefresh] = useState(0), [busy, setBusy] = useState(false), [retry, setRetry] = useState(false)
    const [planner, setPlanner] = useState<"generate" | "import" | "edit" | null>(null), [session, setSession] = useState<CompanionEntry | null>(null), [history, setHistory] = useState(false)
    const sessionBack = useRef<(() => void) | null>(null)
    const locked = useRef(false), previousToday = useRef(today), alive = useRef(true)
    const pending = useRef<CompanionAction | null>(null), callbacks = useRef(c); callbacks.current = c
    const week = trainingWeek(selected), from = week[0], to = shiftCalendarDay(week[6], 1)
    const profileId = c.state?.profile?.id
    const stateSignature = (c.state?.entries ?? []).filter(entry => entry.kind === "workout").map(entry => `${entry.id}:${entry.version}`).join(",")
    useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
    useEffect(() => { if (previousToday.current !== today) { setSelected(value => value === previousToday.current ? today : value); previousToday.current = today } }, [today])
    useEffect(() => {
        if (!active || !profileId) return
        let current = true
        setLoadError("")
        getWorkoutLibrary(from, to).then(result => { if (current) { setLibrary(result.entries); setLoaded(true) } }).catch(failure => { if (current) { const message = getErrorMessage(failure); setLoadError(message); showAlert(message) } })
        return () => { current = false }
    }, [active, from, to, profileId, c.state?.profile?.version, stateSignature, refresh, c.clock])
    const entries = mergeTrainingEntries(library, c.state?.entries ?? [])
    const plan = c.state?.mentor?.workout_plan ?? c.state?.profile?.data.workout_plan
    const days = scheduledTraining(plan, selected), day = days[Math.min(block, days.length - 1)]
    const current = entries.find(entry => trainingEntryDay(entry, c.clock) === selected && (!day || entry.data.workout?.plan_day_key === day.key))
    const running = entries.find(entry => entry.data.workout?.status === "in_progress")
    const target = current ?? running
    const disabled = busy || c.busy || retry
    const choose = (date: string) => { if (disabled) return; setSelected(date); setBlock(0) }
    const updated = (entry: CompanionEntry) => { setLibrary(value => mergeTrainingEntries(value, [entry])); setRefresh(value => value + 1) }
    const start = async () => {
        if (locked.current || callbacks.current.busy) return
        if (!pending.current) {
            if (target) { setSession(target); return }
            if (!day || selected !== today || !loaded || loadError || !plan) return
            const validation = validateTrainingPlan(plan)
            if (validation) { showAlert(validation); return }
            const instant = mentorHomeData(callbacks.current.state, callbacks.current.clock).instant
            pending.current = { kind: "entry", request_key: requestKey(), entry: { kind: "workout", occurred_at: instant, workout: beginTraining(day, selected, instant) } }
        }
        locked.current = true; setBusy(true)
        try {
            const action = pending.current
            const state = await callbacks.current.perform(action)
            const workout = action.entry!.workout!
            let saved = state.entries?.find(entry => entry.data.workout?.plan_day_key === workout.plan_day_key && entry.data.workout?.scheduled_date === workout.scheduled_date)
            if (!saved) saved = (await getWorkoutLibrary(from, to)).entries.find(entry => entry.data.workout?.plan_day_key === workout.plan_day_key && entry.data.workout?.scheduled_date === workout.scheduled_date)
            if (!saved) throw new Error(mt("Не удалось подтвердить сохранение. Повторите запрос."))
            pending.current = null
            if (alive.current) { updated(saved); setSession(saved); setRetry(false) }
        } catch (failure) {
            if (alive.current) {
                if (failure instanceof CompanionActionCancelled) { pending.current = null; setRetry(false) }
                else { showAlert(getErrorMessage(failure)); setRetry(true) }
            }
        } finally { locked.current = false; if (alive.current) setBusy(false) }
    }
    const checkSavedStart = async () => {
        if (locked.current || callbacks.current.busy) return
        locked.current = true; setBusy(true)
        try {
            const result = await getWorkoutLibrary(from, to)
            if (!alive.current) return
            setLibrary(result.entries); setLoaded(true); setLoadError("")
            const expected = pending.current?.entry?.workout
            const saved = result.entries.find(entry => expected && entry.data.workout?.plan_day_key === expected.plan_day_key && entry.data.workout?.scheduled_date === expected.scheduled_date)
            pending.current = null; setRetry(false)
            if (saved) setSession(saved)
            else showAlert(mt("Запись не найдена. Можно начать тренировку заново."))
        } catch (failure) { if (alive.current) showAlert(getErrorMessage(failure)) }
        finally { locked.current = false; if (alive.current) setBusy(false) }
    }
    const closeModal = () => { if (!locked.current && !callbacks.current.busy) { setPlanner(null); setHistory(false) } }
    const label = retry ? mt("Повторить сохранение") : target ? mt(target.data.workout?.status === "completed" ? "Посмотреть тренировку" : "Продолжить тренировку") : selected > today ? mt("Тренировка запланирована") : selected < today ? mt("Нет записи за этот день") : day ? mt("Начать тренировку") : mt("День отдыха")
    const showDate = (date: string) => mentorDateLabel(new Date(`${date}T12:00:00Z`), { day: "numeric", month: "long" })
    const openPlanner = (mode: "generate" | "import" | "edit") => { if (!disabled) { setPlanner(mode) } }
    return <View style={styles.screen}>
        <MentorHomeHeader title={mt("Тренировки")} onBack={onClose} onSettings={onSettings} />
        {!plan ? <View style={[styles.body, styles.fill, { justifyContent: "center", gap: 28 }]}>
            <TrainingIcon name="workout" size={58} />
            <TrainingHeading title={mt("Ваш план тренировок")} subtitle={mt("Составим программу вместе или добавим вашу")} />
            <TrainingAction label={mt("Составить план с нами")} onPress={() => openPlanner("generate")} disabled={disabled} />
            <TrainingAction label={mt("Добавить свой план")} secondary onPress={() => openPlanner("import")} disabled={disabled} />
            {running ? <TrainingAction label={mt("Продолжить тренировку")} secondary onPress={() => setSession(running)} /> : null}
            {entries.length ? <TrainingAction label={mt("История тренировок")} secondary onPress={() => setHistory(true)} /> : null}
        </View> : <>
            <View style={[styles.body, { paddingBottom: 4, gap: 14 }]}>
                <View style={styles.spread}><TrainingHeading title={mt(selected === today ? "Сегодня" : "Тренировки")} /><Pressable accessibilityRole="button" accessibilityLabel={mt("Изменить план")} disabled={disabled} onPress={() => openPlanner("edit")} style={styles.iconButton}><TrainingIcon name="edit" /></Pressable></View>
                <View style={styles.spread}><Pressable accessibilityRole="button" accessibilityLabel={mt("Предыдущая неделя")} disabled={disabled} style={styles.iconButton} onPress={() => choose(shiftCalendarDay(selected, -7))}><TrainingIcon name="left" /></Pressable><Text style={[styles.listValue, { color: colors.text }]}>{showDate(from)} — {showDate(week[6])}</Text><Pressable accessibilityRole="button" accessibilityLabel={mt("Следующая неделя")} disabled={disabled} style={styles.iconButton} onPress={() => choose(shiftCalendarDay(selected, 7))}><TrainingIcon name="right" /></Pressable></View>
                <View style={[styles.row, { gap: 0 }]}>{week.map((date, index) => <Pressable key={date} accessibilityRole="button" accessibilityLabel={showDate(date)} accessibilityState={{ selected: selected === date }} onPress={() => choose(date)} style={styles.day}>
                    <Text style={[styles.caption, { color: colors.muted }]}>{mt(trainingWeekdays[index])}</Text><View style={[styles.dayButton, { backgroundColor: selected === date ? colors.greenBright : "transparent" }]}><Text style={[styles.listValue, { color: selected === date ? "#FFFFFF" : colors.text }]}>{Number(date.slice(-2))}</Text></View><View style={[styles.dot, { backgroundColor: entries.some(entry => trainingEntryDay(entry, c.clock) === date && entry.data.workout?.status === "completed") ? colors.green : scheduledTraining(plan, date).length ? colors.muted : "transparent" }]} />
                </Pressable>)}</View>
                {days.length > 1 ? <View style={styles.row}>{days.map((item, index) => <TrainingAction key={item.key} label={item.name} secondary disabled={disabled || block === index} onPress={() => setBlock(index)} />)}</View> : null}
                <Text style={[styles.section, { color: colors.text }]}>{current?.data.workout?.name ?? day?.name ?? mt("День отдыха")}</Text>
                <Text style={[styles.caption, { color: colors.muted }]}>{day ? mt("Упражнений: {0}", [day.exercises.length]) + (day.duration_minutes ? ` · ${mt("{0} мин", [day.duration_minutes])}` : "") : mt("Можно отдохнуть и восстановиться")}</Text>
                {running && !current ? <Text style={[styles.caption, { color: colors.muted }]}>{mt("Не закончена тренировка: {0}", [running.data.workout!.name])}</Text> : null}
            </View>
            <ScrollView style={styles.fill} contentContainerStyle={[styles.body, { paddingTop: 0 }]} keyboardShouldPersistTaps="handled">
                {(current?.data.workout?.exercises ?? day?.exercises ?? []).map((exercise, index) => {
                    const weight = lastTrainingWeight(exercise, entries, current?.occurred_at ?? mentorHomeData(c.state, c.clock).instant)
                    const prescription = "target_sets" in exercise ? trainingRepLabel(exercise) : typeof exercise.sets === "number" ? trainingRepLabel({ ...exercise, sets: exercise.sets }) : ""
                    return <View key={exercise.key} style={[styles.listRow, { borderBottomColor: colors.border }]}><Text style={[styles.caption, { color: colors.muted, width: 20 }]}>{index + 1}</Text><View style={[styles.fill, { gap: 3 }]}><Text style={[styles.listTitle, { color: colors.text }]}>{exercise.name}</Text>{weight != null ? <Text style={[styles.caption, { color: colors.muted }]}>{mt("Последний вес: {0} кг", [weight])}</Text> : null}</View><Text style={[styles.listValue, { color: colors.muted }]}>{prescription}{exercise.target_weight_kg != null ? " · " + mt("{0} кг", [mentorNumber(Number(exercise.target_weight_kg))]) : ""}</Text></View>
                })}
            </ScrollView>
            <View style={[styles.footer, { paddingBottom: 14 }]}>
                {loadError && !retry ? <TrainingAction label={mt("Повторить загрузку")} secondary onPress={() => setRefresh(value => value + 1)} /> : null}
                <TrainingAction label={mt("История тренировок")} secondary disabled={disabled} onPress={() => setHistory(true)} />
                <TrainingAction label={label} busy={busy} disabled={c.busy || !retry && !target && (!day || selected !== today || !loaded || !!loadError)} onPress={() => void start()} />
                {retry ? <TrainingAction label={mt("Проверить сохранённые тренировки")} secondary disabled={busy} onPress={() => void checkSavedStart()} /> : null}
            </View>
        </>}
        <Modal visible={!!planner || !!session || history} animationType="slide" presentationStyle="fullScreen" onRequestClose={() => { if (session) sessionBack.current?.(); else closeModal() }}>{planner ? <AppFormLayout style={styles.fill}><MentorTrainingPlan key={planner} controller={c} mode={planner} today={today} onClose={closeModal} onSaved={() => { setPlanner(null); setSelected(today); setRefresh(value => value + 1) }} /></AppFormLayout> : session ? <AppFormLayout style={styles.fill}><MentorTrainingSession key={session.id} controller={c} entry={session} registerBack={handler => { sessionBack.current = handler }} onUpdated={updated} onClose={() => setSession(null)} /></AppFormLayout> : history ? <TrainingFrame title={mt("История тренировок")} onBack={closeModal} footer={<TrainingAction label={mt("Готово")} onPress={closeModal} />}><ScrollView contentContainerStyle={styles.body}>
            {!entries.length ? <Text style={[styles.subtitle, { color: colors.muted }]}>{mt("Пока нет тренировок")}</Text> : null}
            {entries.map(entry => <Pressable key={entry.id} accessibilityRole="button" onPress={() => { setHistory(false); setSession(entry) }} style={[styles.listRow, { borderBottomColor: colors.border }]}><View style={[styles.fill, { gap: 4 }]}><Text style={[styles.listTitle, { color: colors.text }]}>{entry.data.workout!.name}</Text><Text style={[styles.caption, { color: colors.muted }]}>{showDate(trainingEntryDay(entry, c.clock))} · {mt(entry.data.workout!.status === "completed" ? "Завершена" : entry.data.workout!.paused_at ? "На паузе" : "Не закончена")}</Text></View><TrainingIcon name="right" /></Pressable>)}
            <Text style={[styles.caption, { color: colors.muted }]}>{mt("Более ранние записи можно открыть, выбрав неделю на главном экране")}</Text>
        </ScrollView></TrainingFrame> : null}</Modal>
    </View>
}
