import { mentorText as mt, mentorLocale, mentorDateLabel } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useEffect, useRef, useState } from "react"
import { Alert, Switch, View } from "react-native"
import type { CompanionEntry, Workout, WorkoutPlan } from "@/services/api/companion"
import { getCompanionEntries, requestKey } from "@/services/api/companion"
import type { useCompanion } from "@/screens/chat/companion"
import { companionCalendarDay, shiftCalendarDay } from "@/screens/chat/companion-timezones"
import { canFinishWorkout, numeric, startWorkout, workoutTotals } from "@/screens/chat/mentor-data"
import { MentorButton as Button, MentorField as Field, MentorText as Copy, mentorStyles as styles } from "@/screens/chat/mentor-ui"

type Controller = ReturnType<typeof useCompanion>
const days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
export function MentorWorkouts({ controller: c, entries, onChanged }: { controller: Controller; entries: CompanionEntry[]; onChanged: () => Promise<void> }) {
    useLanguage()
    const plan = c.state?.mentor?.workout_plan
    const today = c.state?.mentor?.today.date ?? companionCalendarDay(new Date().toISOString(), c.clock)
    const weekday = (new Date(`${today}T12:00:00Z`).getUTCDay() + 6) % 7
    const [editing, setEditing] = useState(false)
    const [activeId, setActiveId] = useState<number | null>(null)
    const sessions = entries.filter(entry => entry.kind === "workout")
    const active = sessions.find(entry => entry.id === activeId) ?? sessions.find(entry => entry.data.workout?.status === "in_progress")
    const keys = useRef(new Map<string, string>())
    const start = (day: WorkoutPlan["days"][number]) => void c.attempt(async () => {
        const identity = `${day.key}:${today}`
        const key = keys.current.get(identity) ?? requestKey()
        keys.current.set(identity, key)
        const state = await c.perform({ kind: "entry", request_key: key, entry: { kind: "workout", occurred_at: new Date().toISOString(), workout: startWorkout(day, today) } })
        keys.current.delete(identity)
        setActiveId(state.entries?.find(entry => entry.data.workout?.status === "in_progress")?.id ?? null)
        await onChanged()
    })
    if (editing) return <WorkoutPlanEditor controller={c} onClose={() => setEditing(false)} onChanged={onChanged} />
    return <>
        <Copy heading>{mt("Тренировки")}</Copy>
        {active ? <WorkoutSession key={active.id} entry={active} controller={c} onChanged={onChanged} /> : null}
        <View style={styles.section}><Copy heading>{plan?.name || mt("План недели")}</Copy>
            {!plan ? <Copy muted>{mt("План тренировок ещё не сохранён.")}</Copy> : days.map(label => mt(label)).map((label, index) => <View key={label} style={styles.row}><Copy>{label}</Copy><View style={{ flex: 1, gap: 8 }}>{plan.days.filter(day => day.weekdays.includes(index)).map(day => <View key={day.key} style={{ gap: 6 }}><Copy>{day.name} · {day.exercises.length} {mt(" упражнений")}</Copy><Button label={index === weekday ? mt("Начать тренировку") : mt("Запланировано на {0}", [label])} disabled={index !== weekday || c.busy || !!active && active.data.workout?.status === "in_progress" || today < plan.start_date || !!plan.end_date && today > plan.end_date} onPress={() => start(day)} /></View>)}{!plan.days.some(day => day.weekdays.includes(index)) ? <Copy muted>{mt("Не запланировано")}</Copy> : null}</View></View>)}
            <Button label={plan ? mt("Изменить план недели") : mt("Добавить свой план")} onPress={() => setEditing(true)} />
        </View>
        <View style={styles.section}><Copy heading>{mt("История тренировок")}</Copy>{!sessions.length ? <Copy muted>{mt("Пока нет записанных тренировок.")}</Copy> : sessions.map(entry => <Button key={entry.id} label={`${entry.data.workout?.name} · ${mentorDateLabel(new Date(entry.occurred_at))} · ${entry.data.workout?.status === "completed" ? mt("завершена") : mt("в процессе")}`} onPress={() => setActiveId(entry.id)} />)}</View>
    </>
}

function WorkoutSession({ entry, controller: c, onChanged }: { entry: CompanionEntry; controller: Controller; onChanged: () => Promise<void> }) {
    useLanguage()
    const [workout, setWorkout] = useState<Workout>(entry.data.workout!)
    const [saved, setSaved] = useState(entry)
    const [notice, setNotice] = useState("")
    const retry = useRef<{ signature: string; key: string } | null>(null)
    useEffect(() => {
        if (entry.version > saved.version && entry.data.workout) { setSaved(entry); setWorkout(entry.data.workout); retry.current = null }
    }, [entry, saved.version])
    const totals = workoutTotals(workout)
    const current = Math.min(workout.current_exercise_index, workout.exercises.length - 1)
    const exercise = workout.exercises[current]
    const target = c.state?.mentor?.workout_plan?.days.find(day => day.key === workout.plan_day_key)?.exercises.find(item => item.key === exercise?.key)
    const completed = workout.status === "completed"
    const persist = (next: Workout) => void c.attempt(async () => {
        const signature = JSON.stringify(next)
        if (retry.current?.signature !== signature) retry.current = { signature, key: requestKey() }
        const result = await c.perform({ kind: "entry", request_key: retry.current.key, resource_id: saved.id, expected_version: saved.version, entry: { ...saved.data, workout: next } })
        const day = companionCalendarDay(saved.occurred_at, c.clock)
        const updated = result.entries?.find(value => value.id === saved.id) ?? (await getCompanionEntries(day, shiftCalendarDay(day, 1), "workout")).entries.find(value => value.id === saved.id)
        if (!updated?.data.workout) { await c.refresh(); throw new Error(mt("Запись отправлена, но подтверждение не загрузилось. Обновите данные перед следующим изменением.")) }
        setSaved(updated); setWorkout(updated.data.workout)
        retry.current = null; setNotice(mt("Сохранено"))
        await onChanged()
    })
    const updateSet = (index: number, patch: Partial<Workout["exercises"][number]["sets"][number]>) => {
        setNotice("")
        setWorkout(value => ({ ...value, exercises: value.exercises.map((item, position) => position === current ? { ...item, sets: item.sets.map((set, setIndex) => setIndex === index ? { ...set, ...patch } : set) } : item) }))
    }
    return <View style={styles.section}>
        <Copy heading>{workout.name}</Copy><Copy>{completed ? mt("Завершена") : mt("Упражнение {0} из {1}", [current + 1, workout.exercises.length])}</Copy>
        {exercise ? <><Copy heading>{exercise.name}</Copy>{target ? <Copy muted>{mt("План: ")}{target.sets} {mt(" подходов · ")}{target.target_reps ?? mt("не задано")} {mt(" повторений · ")}{target.target_weight_kg ?? mt("не задано")} {mt(" кг")}</Copy> : null}{exercise.sets.map((set, index) => <View key={index} style={styles.row}>
            <Copy>{index + 1}</Copy><Field label={mt("Вес, кг")} numeric value={set.weight_kg} disabled={completed || c.busy} onChange={text => updateSet(index, { weight_kg: text.trim() ? text.replace(",", ".") : null, completed: false })} /><Field label={mt("Повторения")} numeric value={set.reps} disabled={completed || c.busy} onChange={text => updateSet(index, { reps: numeric(text), completed: false })} />
            <Switch accessibilityLabel={mt("Подход {0} выполнен", [index + 1])} value={set.completed} disabled={completed || c.busy || numeric(set.weight_kg) == null || Number(set.weight_kg) < 0 || !Number.isInteger(set.reps) || Number(set.reps) < 1} onValueChange={value => updateSet(index, { completed: value })} />
        </View>)}</> : null}
        <View style={styles.row}>{workout.exercises.map((item, index) => <Button key={item.key} label={`${index + 1}. ${item.name}`} onPress={() => setWorkout({ ...workout, current_exercise_index: index })} />)}</View>
        <Copy>{totals.sets} {mt(" подходов · ")}{totals.reps} {mt(" повторений · ")}{totals.volume.toLocaleString(mentorLocale())} {mt(" кг объёма")}</Copy>
        <Field label={mt("Длительность, минут")} numeric value={Math.round(workout.duration_seconds / 60)} disabled={completed || c.busy} onChange={text => { setNotice(""); setWorkout({ ...workout, duration_seconds: Math.max(0, Math.round((numeric(text) ?? 0) * 60)) }) }} />
        {!completed ? <><Button label={mt("Сохранить подходы")} primary disabled={c.busy} onPress={() => persist(workout)} />
            {current < workout.exercises.length - 1 ? <Button label={mt("Сохранить и к следующему упражнению")} disabled={c.busy} onPress={() => persist({ ...workout, current_exercise_index: current + 1 })} /> : null}
            <Button label={mt("Завершить тренировку")} disabled={c.busy || !canFinishWorkout(workout)} onPress={() => Alert.alert(mt("Завершить тренировку?"), mt("{0} выполненных подходов, {1} повторений, {2} кг объёма. Невыполненные подходы не войдут в итоги.", [totals.sets, totals.reps, totals.volume]), [{ text: mt("Отмена"), style: "cancel" }, { text: mt("Завершить"), onPress: () => persist({ ...workout, status: "completed", current_exercise_index: workout.exercises.length }) }])} /></> : null}
        {notice ? <Copy muted>{notice}</Copy> : null}
    </View>
}

function WorkoutPlanEditor({ controller: c, onClose, onChanged }: { controller: Controller; onClose: () => void; onChanged: () => Promise<void> }) {
    useLanguage()
    const [plan, setPlan] = useState<WorkoutPlan>(c.state?.mentor?.workout_plan ?? { name: "", start_date: c.state?.mentor?.today.date ?? companionCalendarDay(new Date().toISOString(), c.clock), end_date: null, days: [] })
    const key = useRef(requestKey())
    const update = (next: WorkoutPlan) => { key.current = requestKey(); setPlan(next) }
    const changeDay = (index: number, patch: Partial<WorkoutPlan["days"][number]>) => update({ ...plan, days: plan.days.map((day, i) => i === index ? { ...day, ...patch } : day) })
    const valid = plan.name.trim() && plan.days.length && plan.days.every(day => day.name.trim() && day.weekdays.length && day.exercises.length && day.exercises.every(exercise => exercise.name.trim() && Number.isInteger(exercise.sets) && exercise.sets >= 1 && exercise.sets <= 30))
    return <><Copy heading>{mt("Мой план тренировок")}</Copy><Field label={mt("Название плана")} value={plan.name} onChange={name => update({ ...plan, name })} /><Field label={mt("Начало, ГГГГ-ММ-ДД")} value={plan.start_date} onChange={start_date => update({ ...plan, start_date })} /><Field label={mt("Конец, ГГГГ-ММ-ДД (необязательно)")} value={plan.end_date} onChange={end_date => update({ ...plan, end_date: end_date || null })} />
        {plan.days.map((day, index) => <View key={day.key} style={styles.section}><Field label={mt("Название тренировки")} value={day.name} onChange={name => changeDay(index, { name })} />
            <View style={styles.row}>{days.map(label => mt(label)).map((label, weekday) => <View key={label} style={{ alignItems: "center" }}><Copy>{label}</Copy><Switch accessibilityLabel={`${day.name || mt("Тренировка")}: ${label}`} value={day.weekdays.includes(weekday)} onValueChange={value => changeDay(index, { weekdays: value ? [...day.weekdays, weekday] : day.weekdays.filter(n => n !== weekday) })} /></View>)}</View>
            {day.exercises.map((exercise, exerciseIndex) => {
                const change = (patch: Partial<typeof exercise>) => changeDay(index, { exercises: day.exercises.map((value, i) => i === exerciseIndex ? { ...value, ...patch } : value) })
                return <View key={exercise.key} style={styles.section}><Field label={mt("Упражнение")} value={exercise.name} onChange={name => change({ name })} /><View style={styles.row}><Field label={mt("Подходов")} value={exercise.sets} numeric onChange={text => change({ sets: numeric(text) ?? 0 })} /><Field label={mt("Повторений (план)")} value={exercise.target_reps} numeric onChange={text => change({ target_reps: numeric(text) })} /><Field label={mt("Вес, кг (план)")} value={exercise.target_weight_kg} numeric onChange={text => change({ target_weight_kg: text.trim() ? text.replace(",", ".") : null })} /></View><Button label={mt("Удалить упражнение")} onPress={() => changeDay(index, { exercises: day.exercises.filter((_, i) => i !== exerciseIndex) })} /></View>
            })}
            <Button label={mt("Добавить упражнение")} onPress={() => changeDay(index, { exercises: [...day.exercises, { key: requestKey(), name: "", sets: 1, target_reps: null, target_weight_kg: null }] })} /><Button label={mt("Удалить тренировку из плана")} onPress={() => update({ ...plan, days: plan.days.filter((_, i) => i !== index) })} /></View>)}
        <Button label={mt("Добавить тренировочный день")} onPress={() => update({ ...plan, days: [...plan.days, { key: requestKey(), name: "", weekdays: [], exercises: [] }] })} />
        <Button label={mt("Сохранить план недели")} primary disabled={c.busy || !valid} onPress={() => void c.attempt(async () => { await c.perform({ kind: "workout_plan", expected_version: c.state?.profile?.version, request_key: key.current, workout_plan: plan }); await onChanged(); onClose() })} /><Button label={mt("Отмена")} onPress={onClose} />
    </>
}
