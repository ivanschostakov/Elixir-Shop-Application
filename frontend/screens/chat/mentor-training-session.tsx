import { useEffect, useRef, useState } from "react"
import { Alert, Pressable, ScrollView, Text, View } from "react-native"
import { mentorText as mt, mentorNumber } from "@/i18n/mentor-translations"
import type { useCompanion } from "@/screens/chat/companion"
import { CompanionActionCancelled } from "@/screens/chat/companion-consent"
import { companionCalendarDay, shiftCalendarDay } from "@/screens/chat/companion-timezones"
import { canFinishWorkout, workoutTotals } from "@/screens/chat/mentor-data"
import { mentorHomeData } from "@/screens/chat/mentor-home-data"
import { trainingElapsed, trainingRepLabel, trainingSessionDraft, trainingSessionPayload, trainingTimer, type TrainingSessionDraft } from "@/screens/chat/mentor-training-data"
import { TrainingAction, TrainingField, TrainingFrame, TrainingHeading, TrainingIcon, trainingStyles as styles } from "@/screens/chat/mentor-training-ui"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { getCompanionEntries, requestKey, type CompanionAction, type CompanionEntry } from "@/services/api/companion"
import { getErrorMessage } from "@/utils/errors"

type Controller = ReturnType<typeof useCompanion>
export function MentorTrainingSession({ controller: c, entry, onUpdated, onClose, registerBack }: { controller: Controller; entry: CompanionEntry; onUpdated: (entry: CompanionEntry) => void; onClose: () => void; registerBack?: (handler: (() => void) | null) => void }) {
    const colors = useMentorPalette()
    const callbacks = useRef({ c, onUpdated, onClose }); callbacks.current = { c, onUpdated, onClose }
    const currentTime = () => Date.parse(mentorHomeData(callbacks.current.c.state, callbacks.current.c.clock).instant)
    const initialize = (record: CompanionEntry) => {
        const result = trainingSessionDraft(record.data.workout!)
        if (result.status === "in_progress" && !result.timer_started_at) result.timer_started_at = new Date(currentTime() - result.duration_seconds * 1000).toISOString()
        if (result.status === "completed") result.current_exercise_index = 0
        return result
    }
    const [draft, setDraft] = useState<TrainingSessionDraft>(() => initialize(entry)), [now, setNow] = useState(currentTime)
    const draftRef = useRef(draft), record = useRef(entry), clean = useRef(JSON.stringify(draft))
    const [error, setError] = useState(""), [busy, setBusy] = useState(false), [retry, setRetry] = useState(false)
    const locked = useRef(false), alive = useRef(true)
    const pending = useRef<{ action: CompanionAction; close: boolean } | null>(null)
    useEffect(() => { alive.current = true; const timer = setInterval(() => setNow(currentTime()), 1000); return () => { alive.current = false; clearInterval(timer) } }, [])
    const change = (next: TrainingSessionDraft) => { draftRef.current = next; setDraft(next); setNow(currentTime()); setError("") }
    const disabled = busy || c.busy || retry, readonly = draft.status === "completed"
    const index = Math.min(draft.current_exercise_index, draft.exercises.length - 1), exercise = draft.exercises[index]
    const elapsed = trainingElapsed(draft, now)
    const rest = Math.max(0, Math.ceil((Date.parse(draft.rest_ends_at ?? "") - now) / 1000) || 0)
    const sendPending = async () => {
        if (locked.current || callbacks.current.c.busy || !pending.current) return
        locked.current = true; setBusy(true); setError("")
        try {
            const request = pending.current
            const state = await callbacks.current.c.perform(request.action)
            let saved = state.entries?.find(item => item.id === record.current.id)
            if (!saved) {
                const day = companionCalendarDay(record.current.occurred_at, callbacks.current.c.clock)
                saved = (await getCompanionEntries(day, shiftCalendarDay(day, 1), "workout")).entries.find(item => item.id === record.current.id)
            }
            if (!saved?.data.workout) throw new Error(mt("Не удалось подтвердить сохранение. Повторите запрос."))
            record.current = saved; pending.current = null
            callbacks.current.onUpdated(saved)
            if (!alive.current) return
            const next = initialize(saved); change(next); clean.current = JSON.stringify(next); setRetry(false)
            if (request.close) callbacks.current.onClose()
        } catch (failure) {
            if (!alive.current) return
            if (failure instanceof CompanionActionCancelled) { pending.current = null; setRetry(false) }
            else { setError(getErrorMessage(failure)); setRetry(true) }
        } finally { locked.current = false; if (alive.current) setBusy(false) }
    }
    const save = (next: TrainingSessionDraft, close = false) => {
        if (locked.current || c.busy || pending.current) return
        try {
            const workout = trainingSessionPayload({ ...next, duration_seconds: trainingElapsed(next, currentTime()) })
            pending.current = { close, action: { kind: "entry", resource_id: record.current.id, expected_version: record.current.version, request_key: requestKey(), entry: { ...record.current.data, workout } } }
            change(next); void sendPending()
        } catch (failure) { setError(getErrorMessage(failure)) }
    }
    const back = () => {
        if (busy || c.busy) return
        if (retry) {
            Alert.alert(mt("Закрыть без сохранения?"), mt("Последние изменения могли не сохраниться. При следующем открытии загрузится запись с сервера."), [{ text: mt("Отмена"), style: "cancel" }, { text: mt("Закрыть"), onPress: onClose }])
            return
        }
        if (readonly || clean.current === JSON.stringify(draftRef.current)) onClose()
        else save(draftRef.current, true)
    }
    useEffect(() => { registerBack?.(back); return () => registerBack?.(null) })
    const reload = () => Alert.alert(mt("Загрузить сохранённую тренировку?"), mt("Несохранённые изменения на этом экране будут заменены."), [{ text: mt("Отмена"), style: "cancel" }, { text: mt("Загрузить"), onPress: async () => {
        if (locked.current) return
        locked.current = true; setBusy(true)
        try {
            const day = companionCalendarDay(record.current.occurred_at, c.clock)
            const saved = (await getCompanionEntries(day, shiftCalendarDay(day, 1), "workout")).entries.find(item => item.id === record.current.id)
            if (!saved?.data.workout) throw new Error(mt("Тренировка больше недоступна"))
            record.current = saved; callbacks.current.onUpdated(saved); pending.current = null
            if (alive.current) { const next = initialize(saved); change(next); clean.current = JSON.stringify(next); setRetry(false) }
        } catch (failure) { if (alive.current) setError(getErrorMessage(failure)) }
        finally { locked.current = false; if (alive.current) setBusy(false) }
    } }])
    const updateSet = (setIndex: number, field: "weight" | "reps", value: string) => change({ ...draft, exercises: draft.exercises.map((item, i) => i === index ? { ...item, sets: item.sets.map((set, j) => j === setIndex ? { ...set, [field]: value, completed: false } : set) } : item) })
    const completeSet = (setIndex: number) => {
        const next: TrainingSessionDraft = { ...draft, exercises: draft.exercises.map((item, i) => i === index ? { ...item, sets: item.sets.map((set, j) => j === setIndex ? { ...set, completed: !set.completed } : set) } : item) }
        if (next.exercises[index].sets[setIndex].completed) next.rest_ends_at = new Date(currentTime() + (exercise.rest_seconds ?? 60) * 1000).toISOString()
        save(next)
    }
    const finish = () => {
        try {
            const workout = trainingSessionPayload(draftRef.current)
            if (!canFinishWorkout(workout)) { setError(mt("Отметьте хотя бы один выполненный подход")); return }
            const totals = workoutTotals(workout)
            Alert.alert(mt("Завершить тренировку?"), mt("В историю попадут только выполненные подходы: {0}", [totals.sets]), [{ text: mt("Продолжить"), style: "cancel" }, { text: mt("Завершить"), onPress: () => save({ ...draftRef.current, status: "completed", rest_ends_at: null, current_exercise_index: draftRef.current.exercises.length }, true) }])
        } catch (failure) { setError(getErrorMessage(failure)) }
    }
    return <TrainingFrame title={mt(readonly ? "Тренировка завершена" : "Тренировка")} onBack={back} footer={<>
        <View style={styles.errorSlot}>{error ? <Text accessibilityRole="alert" numberOfLines={2} style={[styles.error, { color: colors.text }]}>{error}</Text> : null}</View>
        {retry ? <><TrainingAction label={mt("Повторить сохранение")} busy={busy} disabled={c.busy} onPress={() => void sendPending()} /><TrainingAction label={mt("Загрузить сохранённое")} secondary disabled={busy} onPress={reload} /></> : readonly ? <TrainingAction label={mt("Готово")} onPress={onClose} /> : <>
            {index < draft.exercises.length - 1 ? <TrainingAction label={mt("Следующее упражнение")} busy={busy} disabled={c.busy} onPress={() => save({ ...draft, current_exercise_index: index + 1, rest_ends_at: null })} /> : null}
            <TrainingAction label={mt("Завершить тренировку")} secondary={index < draft.exercises.length - 1} busy={busy && index === draft.exercises.length - 1} disabled={disabled} onPress={finish} />
        </>}
    </>}><ScrollView keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" contentContainerStyle={styles.body}>
        <View style={styles.spread}><Text style={[styles.caption, { color: colors.muted }]}>{draft.name}</Text><Text style={[styles.listValue, { color: colors.green }]}>{trainingTimer(elapsed)}</Text></View>
        <TrainingHeading title={exercise.name} subtitle={mt("Упражнение {0} из {1}", [index + 1, draft.exercises.length])} />
        {exercise.target_sets ? <Text style={[styles.subtitle, { color: colors.muted }]}>{mt("По плану: {0}", [trainingRepLabel(exercise)])}{exercise.target_weight_kg != null ? ` · ${mt("{0} кг", [exercise.target_weight_kg])}` : ""}</Text> : null}
        <View style={[styles.row, { paddingHorizontal: 4 }]}><Text style={[styles.caption, { width: 28, color: colors.muted }]}>#</Text><Text style={[styles.caption, { flex: 1, color: colors.muted }]}>{mt("Вес, кг")}</Text><Text style={[styles.caption, { flex: 1, color: colors.muted }]}>{mt("Повторения")}</Text><View style={{ width: 44 }} /></View>
        <View style={{ gap: 10 }}>{exercise.sets.map((set, setIndex) => <View key={setIndex} style={styles.row}><Text style={[styles.listValue, { width: 24, color: colors.muted }]}>{setIndex + 1}</Text><View style={styles.fill}><TrainingField label={mt("Вес в подходе {0}", [setIndex + 1])} value={set.weight} onChange={value => updateSet(setIndex, "weight", value)} numeric disabled={disabled || readonly} maxLength={8} placeholder="—" /></View><View style={styles.fill}><TrainingField label={mt("Повторения в подходе {0}", [setIndex + 1])} value={set.reps} onChange={value => updateSet(setIndex, "reps", value)} numeric disabled={disabled || readonly} maxLength={4} placeholder="—" /></View><Pressable accessibilityRole="checkbox" accessibilityLabel={mt("Подход {0} выполнен", [setIndex + 1])} accessibilityState={{ checked: set.completed, disabled: disabled || readonly }} disabled={disabled || readonly} onPress={() => completeSet(setIndex)} style={[styles.iconButton, { borderRadius: 14, backgroundColor: set.completed ? colors.greenBright : colors.input }]}><TrainingIcon name="check" color={set.completed ? "#FFFFFF" : colors.muted} /></Pressable></View>)}</View>
        {!readonly ? <TrainingAction label={mt("Добавить подход")} secondary disabled={disabled || exercise.sets.length >= 30} onPress={() => change({ ...draft, exercises: draft.exercises.map((item, i) => i === index ? { ...item, sets: [...item.sets, { weight: "", reps: "", completed: false }] } : item) })} /> : null}
        <View style={[styles.spread, { minHeight: 50 }]}><Text style={[styles.subtitle, { color: colors.muted }]}>{mt("Отдых")}</Text><Text style={[styles.section, { color: colors.green }]}>{trainingTimer(rest)}</Text>{rest > 0 && !readonly ? <TrainingAction label={mt("Пропустить")} secondary disabled={disabled} onPress={() => save({ ...draft, rest_ends_at: null })} /> : null}</View>
        {readonly ? <Text style={[styles.subtitle, { color: colors.muted }]}>{mt("Объём: {0} кг", [mentorNumber(workoutTotals(trainingSessionPayload(draft)).volume)])}</Text> : <Text style={[styles.caption, { color: colors.muted }]}>{mt("Для упражнений без отягощения укажите 0 кг")}</Text>}
        <View style={styles.spread}><TrainingAction label={mt("Назад")} secondary disabled={disabled || index === 0} onPress={() => readonly ? change({ ...draft, current_exercise_index: index - 1 }) : save({ ...draft, current_exercise_index: index - 1 })} />{readonly && index < draft.exercises.length - 1 ? <TrainingAction label={mt("Далее")} secondary onPress={() => change({ ...draft, current_exercise_index: index + 1 })} /> : null}</View>
    </ScrollView></TrainingFrame>
}
