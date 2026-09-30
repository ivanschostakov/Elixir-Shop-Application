import { useCallback, useEffect, useRef, useState } from "react"
import { ActivityIndicator, Alert, Platform, Pressable, ScrollView, View } from "react-native"
import { Calendar } from "react-native-calendars"
import Svg, { Circle, Line, Polyline } from "react-native-svg"
import { useRouter } from "expo-router"
import { useTheme } from "@/providers/theme-provider"
import { ProfileIcon, SavedIcon, SmileBubbleIcon } from "@/components/footer/sticky-footer.icons"
import CameraIcon from "@/assets/icons/chat/camera-svgrepo-com.svg"
import MicrophoneIcon from "@/assets/icons/chat/microphone-alt-svgrepo-com.svg"
import { companionDialogue, getCompanionEntries, getCompanionEvents, getCompanionFavoriteMeals, getCompanionSummary, requestKey } from "@/services/api/companion"
import type { CompanionAction, CompanionEntry, CompanionEvent, EntryData, Measurement, Summary } from "@/services/api/companion"
import type { AIAttachmentRead, AIMessageRead } from "@/services/api/ai-chat.types"
import type { useCompanion } from "@/screens/chat/companion"
import { calendarDate, companionCalendarDay, formatCompanionDate, localDateTime, localEntryTimestamp } from "@/screens/chat/companion-timezones"
import { chartPoints, goalLabels, measurementLabels, numeric, recordedMean, repeatMeal, workoutTotals } from "@/screens/chat/mentor-data"
import type { MentorPage } from "@/screens/chat/mentor-data"
import { MentorWorkouts } from "@/screens/chat/mentor-workouts"
import { MentorPhotos } from "@/screens/chat/mentor-photos"
import { MentorButton as Button, MentorField as Field, MentorTabs as Tabs, MentorText as Copy, mentorStyles as styles } from "@/screens/chat/mentor-ui"

type Controller = ReturnType<typeof useCompanion>
export type MentorComposeMode = "text" | "photo" | "voice"
export const mentorNavigation = { today: "Сегодня", nutrition: "Питание", workouts: "Тренировки", course: "Мой курс", more: "Ещё" } as const
export function MentorNavigation({ controller: c }: { controller: Controller }) {
    return <Tabs items={mentorNavigation} value={c.mentorPage && c.mentorPage in mentorNavigation ? c.mentorPage as keyof typeof mentorNavigation : null} onChange={page => { c.setEditor(null); c.setMentorPage(page) }} />
}

export function MentorWorkspace({ controller: c, onCompose, onPrompt, photoMessages = [], renderPhotoAttachments = () => null }: { controller: Controller; onCompose: (mode: MentorComposeMode, text: string) => void; onPrompt: (text: string) => Promise<unknown>; photoMessages?: AIMessageRead[]; renderPhotoAttachments?: (attachments: AIAttachmentRead[]) => React.ReactNode }) {
    const { palette } = useTheme()
    const router = useRouter()
    const [entries, setEntries] = useState<CompanionEntry[]>(c.state?.entries ?? [])
    const [loading, setLoading] = useState(false)
    const [days, setDays] = useState<7 | 30>(7)
    const [mealMode, setMealMode] = useState<"recent" | "favorites" | "history">("recent")
    const [favorites, setFavorites] = useState<CompanionEntry[]>([])
    const [moreFavorites, setMoreFavorites] = useState(false)
    const [addFood, setAddFood] = useState(false)
    const [measurementOpen, setMeasurementOpen] = useState(false)
    const [repeating, setRepeating] = useState<CompanionEntry | null>(null)
    const [progressTab, setProgressTab] = useState<"weight" | "nutrition" | "workouts" | "course" | "measurements" | "photos">("weight")
    const [summary, setSummary] = useState<Summary | null>(null)
    const [selectedWeight, setSelectedWeight] = useState<number | null>(null)
    const [chartWidth, setChartWidth] = useState(320)
    const [historyFrom, setHistoryFrom] = useState(calendarDate(-29))
    const [historyTo, setHistoryTo] = useState(calendarDate(1))
    const [historyRange, setHistoryRange] = useState({ from: calendarDate(-29), to: calendarDate(1) })
    const [progressEntries, setProgressEntries] = useState<CompanionEntry[]>([])
    const [weeklyEntries, setWeeklyEntries] = useState<CompanionEntry[]>([])
    const sequence = useRef(0)
    const invalidateLoads = useCallback(() => { sequence.current++ }, [])
    const keys = useRef(new Map<string, string>())
    const callbacks = useRef(c); callbacks.current = c
    const load = useCallback(async () => {
        const token = ++sequence.current
        setLoading(true)
        try {
            const history = c.mentorPage === "nutrition" && mealMode === "history"
            const result = await getCompanionEntries(history ? historyRange.from : calendarDate(-29), history ? historyRange.to : calendarDate(1), c.mentorPage === "workouts" ? "workout" : "meal")
            if (token === sequence.current) setEntries(result.entries)
        } finally { if (token === sequence.current) setLoading(false) }
    }, [historyRange, c.mentorPage, mealMode])
    useEffect(() => { void callbacks.current.attempt(load); return invalidateLoads }, [load, c.clock, c.state, invalidateLoads])
    useEffect(() => {
        if (mealMode !== "favorites" || c.mentorPage !== "nutrition") return
        let cancelled = false
        void getCompanionFavoriteMeals().then(result => { if (!cancelled) { setFavorites(result.entries); setMoreFavorites(result.may_have_more) } }).catch(error => { if (!cancelled) callbacks.current.setError(error instanceof Error ? error.message : "Не удалось загрузить избранное") })
        return () => { cancelled = true }
    }, [mealMode, c.mentorPage, c.state])
    useEffect(() => {
        if (c.mentorPage !== "progress") return
        let cancelled = false
        setSummary(null)
        setProgressEntries([])
        void getCompanionEntries(calendarDate(-6), calendarDate(1), "weight").then(result => { if (!cancelled) setWeeklyEntries(result.entries.filter(entry => Date.parse(entry.occurred_at) <= Date.now())) }).catch(error => { if (!cancelled) callbacks.current.setError(error instanceof Error ? error.message : "Не удалось загрузить средний вес за неделю") })
        const kind = progressTab === "workouts" ? "workout" : progressTab === "measurements" ? "measurement" : "weight"
        void getCompanionEntries(calendarDate(1 - days), calendarDate(1), kind).then(result => { if (!cancelled) setProgressEntries(result.entries) }).catch(error => { if (!cancelled) callbacks.current.setError(error instanceof Error ? error.message : "Не удалось загрузить измерения") })
        void getCompanionSummary(calendarDate(1 - days), calendarDate(1)).then(result => { if (!cancelled) setSummary(result) }).catch(error => { if (!cancelled) callbacks.current.setError(error instanceof Error ? error.message : "Не удалось загрузить отчёт") })
        return () => { cancelled = true }
    }, [days, c.mentorPage, c.clock, c.state, progressTab])
    const save = async (action: CompanionAction) => {
        const identity = JSON.stringify(action)
        const key = keys.current.get(identity) ?? requestKey(); keys.current.set(identity, key)
        await c.perform({ ...action, request_key: key })
        keys.current.delete(identity)
        await load()
    }
    const go = (page: MentorPage) => { setAddFood(false); c.setError(""); c.setMentorPage(page) }
    const compose = (mode: MentorComposeMode, text: string) => { c.setMentorPage(null); onCompose(mode, text) }
    const ask = (text: string) => void c.attempt(async () => { c.setMentorPage(null); await onPrompt(text) })
    const report = () => void c.attempt(async () => { await companionDialogue("progress", days); c.setMentorPage(null); await onPrompt("") })
    const mentor = c.state?.mentor
    const latest = mentor?.latest_weight
    const nutrition = mentor?.today.nutrition
    const tasks = mentor?.today.tasks ?? []
    const sortedEntries = [...entries].sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at))
    const meals = mealMode === "favorites" ? favorites : sortedEntries.filter(entry => entry.kind === "meal")
    const periodEntries = progressEntries.filter(entry => Date.parse(entry.occurred_at) <= Date.now())
    const points = chartPoints(periodEntries, chartWidth)
    const point = points.find(value => value.id === selectedWeight) ?? points[points.length - 1]
    const averageWeight = recordedMean(weeklyEntries, "weight", "weight_kg")
    const targetWeight = numeric(c.state?.profile?.data.target_weight_kg)
    const latestWeight = numeric(latest?.data.weight_kg)
    const page = c.mentorPage
    if (!page) return null
    return <View testID="mentor-workspace" style={[styles.body, { backgroundColor: palette.surface }]}>
        <View style={[styles.row, { justifyContent: "space-between" }]}><View style={{ flex: 1 }}><Copy heading>Наставник ElixirPeptide</Copy></View><Pressable accessibilityRole="button" accessibilityLabel="Вернуться к диалогу" onPress={() => c.setMentorPage(null)} style={{ padding: 12 }}><SmileBubbleIcon color={palette.primary} /></Pressable></View>
        {c.error ? <><Copy>{c.error}</Copy><Button label="Обновить данные" onPress={() => void c.attempt(async () => { await c.refresh(); await load() })} /></> : null}
        {loading || c.busy ? <ActivityIndicator color={palette.primary} /> : null}
        {page === "today" ? <>
            <Copy heading>Ваш план на сегодня</Copy><Copy muted>{new Date().toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" })}</Copy>
            <View style={styles.row}><View style={styles.metric}><Copy muted>Питание</Copy><Copy heading>{nutrition ? `${nutrition.consumed.kcal}${nutrition.target ? ` / ${nutrition.target.kcal}` : ""} ккал` : "Нет записей"}</Copy></View><View style={styles.metric}><Copy muted>Осталось</Copy><Copy heading>{nutrition?.remaining ? `${nutrition.remaining.kcal} ккал` : "Цель не задана"}</Copy></View></View>
            <Copy muted>Приёмов пищи записано сегодня: {c.state?.today?.meals_logged ?? 0}</Copy>
            <Copy>Вес: {latest ? `${latest.data.weight_kg} кг` : "ещё не записан"}{c.state?.profile?.data.target_weight_kg ? ` · цель ${c.state.profile.data.target_weight_kg} кг` : ""}</Copy>
            {latest ? <Copy muted>{formatCompanionDate(latest.occurred_at, c.clock)}</Copy> : null}
            <View style={styles.section}>{tasks.length ? <><Copy>Выполнено {tasks.filter(task => task.status === "done").length} из {tasks.length} запланированных событий</Copy>{tasks.map(task => <View key={task.id} style={styles.row}><View style={{ flex: 1 }}><Copy>{task.label}</Copy><Copy muted>{task.status === "done" ? "Выполнено" : task.status === "skipped" ? "Пропущено" : task.status === "in_progress" ? "В процессе" : task.scheduled_at ? formatCompanionDate(task.scheduled_at, c.clock) : "Запланировано"}</Copy></View><Button label={task.kind === "workout" ? "Тренировка" : "Открыть"} onPress={() => go(task.kind === "workout" ? "workouts" : "course")} /></View>)}</> : <Copy muted>На сегодня нет запланированных событий.</Copy>}</View>
            <Button label="Добавить еду" primary onPress={() => { setAddFood(true); c.setMentorPage("nutrition") }} />
            <View style={styles.row}><View style={{ flex: 1 }}><Button label="Начать тренировку" onPress={() => go("workouts")} /></View><View style={{ flex: 1 }}><Button label="Открыть курс" onPress={() => go("course")} /></View></View>
            <View style={styles.row}><View style={{ flex: 1 }}><Button label="Самочувствие" onPress={() => c.setEditor({ page: "wellbeing" })} /></View><View style={{ flex: 1 }}><Button label="Прогресс" onPress={() => go("progress")} /></View></View><Button label="Скорректировать план" onPress={() => go("adjust")} />
        </> : null}
        {page === "nutrition" ? <>
            <Copy heading>Питание</Copy>
            {nutrition ? <><Copy>{nutrition.consumed.kcal} ккал за сегодня{nutrition.target ? ` из ${nutrition.target.kcal}` : ""}</Copy><View style={styles.row}>{(["protein", "fat", "carbs"] as const).map((key, index) => <View key={key} style={styles.metric}><Copy muted>{["Белки", "Жиры", "Углеводы"][index]}</Copy><Copy>{nutrition.consumed[key]} г{nutrition.target ? ` / ${nutrition.target[key]} г` : ""}</Copy></View>)}</View>{nutrition.remaining ? <Copy>Осталось: {nutrition.remaining.kcal} ккал · Б {nutrition.remaining.protein} · Ж {nutrition.remaining.fat} · У {nutrition.remaining.carbs} г</Copy> : <Button label="Задать ориентиры питания" onPress={() => c.setEditor({ page: "nutrition" })} />}</> : null}
            <Button label="Добавить еду" primary onPress={() => setAddFood(value => !value)} />
            {addFood ? <View style={styles.section}><Button label="Фото еды" icon={<CameraIcon width={22} height={22} color={palette.text} />} onPress={() => compose("photo", "Хочу записать еду по фото. Уточни порцию и предложи запись для подтверждения.")} /><Button label="Рассказать голосом" icon={<MicrophoneIcon width={22} height={22} color={palette.text} />} onPress={() => compose("voice", "")} /><Button label="Написать о еде" onPress={() => compose("text", "Хочу записать еду: ")} /><Button label="Внести КБЖУ вручную" onPress={() => c.setEditor({ page: "meal" })} /></View> : null}
            <Tabs items={{ recent: "Недавние", favorites: "Избранное", history: "История" }} value={mealMode} onChange={setMealMode} />
            {mealMode === "history" ? <View style={styles.row}><Field label="С даты, ГГГГ-ММ-ДД" value={historyFrom} onChange={setHistoryFrom} /><Field label="До даты (не включая)" value={historyTo} onChange={setHistoryTo} /><Button label="Загрузить историю" disabled={loading} onPress={() => setHistoryRange({ from: historyFrom, to: historyTo })} /></View> : null}
            {repeating ? <View style={styles.section}><Copy heading>Повторить приём пищи?</Copy><MealCopy entry={repeating} /><Button label="Подтвердить на сейчас" primary disabled={c.busy} onPress={() => void c.attempt(async () => { await save({ kind: "entry", entry: repeatMeal(repeating, repeating.data.occurred_at) }); setRepeating(null) })} /><Button label="Исправить перед записью" onPress={() => { c.setEditor({ page: "meal", proposal: { kind: "entry", summary: "", entry: repeatMeal(repeating, repeating.data.occurred_at) } }); setRepeating(null) }} /><Button label="Отмена" onPress={() => setRepeating(null)} /></View> : null}
            {!meals.length ? <Copy muted>{mealMode === "favorites" ? "Пока нет избранных блюд." : "В выбранном периоде нет записей о еде."}</Copy> : meals.slice(0, mealMode === "recent" ? 8 : 200).map(entry => <View key={entry.id} style={styles.section}><MealCopy entry={entry} /><Copy muted>{formatCompanionDate(entry.occurred_at, c.clock)}</Copy><View style={styles.row}><Button label="Повторить" disabled={c.busy} onPress={() => setRepeating({ ...entry, data: repeatMeal(entry) })} /><Pressable accessibilityRole="button" accessibilityLabel={entry.data.favorite ? "Убрать из избранного" : "В избранное"} accessibilityState={{ selected: !!entry.data.favorite }} disabled={c.busy} onPress={() => void c.attempt(() => save({ kind: "entry", resource_id: entry.id, expected_version: entry.version, entry: { ...entry.data, favorite: !entry.data.favorite } }))} style={{ padding: 12 }}><SavedIcon color={entry.data.favorite ? "#C34768" : palette.mutedText} /></Pressable><Button label="Исправить" onPress={() => c.setEditor({ page: "meal", entry })} /></View></View>)}
            {mealMode === "favorites" && moreFavorites ? <Copy muted>Показаны последние 200 избранных записей.</Copy> : null}
            {entries.length >= 200 ? <Copy muted>Показаны последние 200 записей. Сузьте период истории.</Copy> : null}
        </> : null}
        {page === "workouts" ? <MentorWorkouts controller={c} entries={entries} onChanged={load} /> : null}
        {page === "course" ? <MentorCourse controller={c} /> : null}
        {page === "progress" ? <>
            <Copy heading>Прогресс за {days} дней</Copy><Copy muted>{calendarDate(1 - days)} – {calendarDate()}</Copy>
            <Tabs items={{ "7": "7 дней", "30": "30 дней" }} value={String(days) as "7" | "30"} onChange={value => setDays(Number(value) as 7 | 30)} />
            <Tabs items={{ weight: "Вес", nutrition: "Питание", workouts: "Тренировки", course: "Курс", measurements: "Замеры", photos: "Фото" }} value={progressTab} onChange={setProgressTab} />
            <Copy muted>Энергия за {days} дней: {summary?.wellbeing?.average_energy == null ? "нет данных" : `${summary.wellbeing.average_energy}/5 · ${summary.wellbeing.energy_measurements ?? "—"} измерений`}</Copy>
            {progressTab === "weight" ? <>
                <Copy heading>{summary?.weight_change_kg != null ? `${Number(summary.weight_change_kg) > 0 ? "+" : ""}${summary.weight_change_kg} кг` : "Недостаточно данных для изменения"}</Copy>
                <Copy muted>Средний вес за 7 дней: {averageWeight.value == null ? "нет измерений" : `${averageWeight.value} кг · ${averageWeight.count} измерений`}</Copy>
                {weeklyEntries.length >= 200 ? <Copy muted>Среднее рассчитано по последним 200 измерениям.</Copy> : null}
                {targetWeight != null && latestWeight != null ? <Copy>Цель: {targetWeight} кг · разница с последним весом: {Math.abs(targetWeight - latestWeight).toFixed(1)} кг</Copy> : null}
                <View onLayout={event => setChartWidth(Math.max(220, event.nativeEvent.layout.width))} style={{ height: 190, width: "100%" }}>
                    {points.length ? <Svg width="100%" height={180} viewBox={`0 0 ${chartWidth} 180`} accessibilityLabel="График измерений веса">
                        {[20, 90, 160].map(y => <Line key={y} x1={20} x2={chartWidth - 20} y1={y} y2={y} stroke={palette.border} />)}
                        <Polyline points={points.map(value => `${value.x},${value.y}`).join(" ")} stroke="#27855F" strokeWidth={3} fill="none" />
                        {points.map(value => <Circle key={value.id} cx={value.x} cy={value.y} r={value.id === point?.id ? 8 : 5} fill={palette.surface} stroke="#27855F" strokeWidth={3} onPress={() => { setSelectedWeight(value.id); return {} }} />)}
                    </Svg> : <Copy muted>В этом периоде нет измерений веса.</Copy>}
                </View>
                {point ? <Copy>{new Date(point.date).toLocaleDateString("ru-RU")} · {point.value} кг</Copy> : null}
                <ScrollView horizontal showsHorizontalScrollIndicator={false}><View style={[styles.row, { flexWrap: "nowrap" }]}>{points.map(value => <Button key={value.id} label={`${new Date(value.date).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}: ${value.value} кг`} onPress={() => setSelectedWeight(value.id)} />)}</View></ScrollView>
                <Copy muted>{summary ? `${summary.weight_measurements} измерений за период. Вес не показывает состав тела.` : "Загружаем сводку…"}</Copy><Button label="Добавить вес" primary onPress={() => c.setEditor({ page: "weight" })} />
            </> : null}
            {progressTab === "nutrition" ? <>{summary ? <><Copy heading>{summary.nutrition.kcal} ккал записано</Copy><Copy>{summary.meals_logged} приёмов пищи за {summary.days_with_meals} дней с записями</Copy><Copy>Б {summary.nutrition.protein} · Ж {summary.nutrition.fat} · У {summary.nutrition.carbs} г</Copy><Copy muted>{summary.coverage_note}</Copy></> : <ActivityIndicator />}</> : null}
            {progressTab === "course" ? <>{summary ? <><Copy>Выполнено {summary.events.done} · пропущено {summary.events.skipped} · без отметки {summary.events.pending}</Copy><Copy muted>{summary.coverage_note}</Copy></> : <ActivityIndicator />}</> : null}
            {progressTab === "workouts" ? <>{summary?.workouts ? <><Copy heading>{summary.workouts.completed} завершённых тренировок</Copy><Copy>{summary.workouts.completed_sets} подходов · {summary.workouts.reps} повторений · {summary.workouts.volume_kg} кг · {Math.round(summary.workouts.duration_seconds / 60)} мин</Copy><Copy muted>{summary.workouts.in_progress} в процессе</Copy></> : null}{periodEntries.filter(entry => entry.kind === "workout").length ? periodEntries.filter(entry => entry.kind === "workout" && entry.data.workout).map(entry => { const workout = entry.data.workout!; const totals = workoutTotals(workout); return <View key={entry.id} style={styles.section}><Copy>{workout.name} · {workout.status === "completed" ? "Завершена" : "В процессе"}</Copy><Copy>{totals.sets} подходов · {totals.volume} кг · {Math.round(workout.duration_seconds / 60)} мин</Copy></View> }) : <Copy muted>Нет записей тренировок в загруженной истории.</Copy>}</> : null}
            {progressTab === "measurements" ? <><Button label="Добавить замеры" primary onPress={() => setMeasurementOpen(true)} />{measurementOpen ? <MeasurementEditor controller={c} save={save} onClose={() => setMeasurementOpen(false)} /> : null}{periodEntries.filter(entry => entry.kind === "measurement").map(entry => <View key={entry.id} style={styles.section}><Copy muted>{formatCompanionDate(entry.occurred_at, c.clock)}</Copy>{Object.entries(entry.data.measurement ?? {}).filter(([, value]) => value != null).map(([key, value]) => <Copy key={key}>{measurementLabels[key as keyof Measurement]}: {value}</Copy>)}</View>)}{!periodEntries.some(entry => entry.kind === "measurement") ? <Copy muted>Замеров пока нет.</Copy> : null}</> : null}
            {progressTab === "photos" ? <><Button label="Добавить фото прогресса" icon={<CameraIcon width={22} height={22} color={palette.text} />} onPress={() => compose("photo", "Фото прогресса. Не оценивай состав тела и здоровье по фотографии.")} /><MentorPhotos controller={c} days={days} messages={photoMessages} renderAttachments={renderPhotoAttachments} /></> : null}
            <Button label={`Отчёт за ${days} дней в диалоге`} onPress={report} disabled={c.busy} />
        </> : null}
        {page === "more" ? <><Copy heading>Мой профиль</Copy><View style={styles.row}><ProfileIcon color={palette.primary} /><Copy>{c.state?.profile?.data.goal ? goalLabels[c.state.profile.data.goal] : "Цель не указана"}{c.state?.profile?.data.custom_goal ? `: ${c.state.profile.data.custom_goal}` : ""}</Copy></View><Copy>Последний вес: {latest ? `${latest.data.weight_kg} кг · ${formatCompanionDate(latest.occurred_at, c.clock)}` : "не записан"}</Copy><Button label="Профиль и цели" onPress={() => c.setEditor({ page: "profile" })} /><Button label="Записать вес" onPress={() => c.setEditor({ page: "weight" })} /><Button label="Прогресс и замеры" onPress={() => go("progress")} /><Button label="Настройки и напоминания" onPress={() => c.setEditor({ page: "settings" })} /><Button label="Дневник" onPress={() => c.setEditor({ page: "journal" })} /><Button label="Написать в поддержку" onPress={() => router.push({ pathname: "/chat", params: { mode: "support" } })} /></> : null}
        {page === "adjust" ? <><Copy heading>Что скорректировать?</Copy><Button label="Цель и профиль" onPress={() => c.setEditor({ page: "profile" })} /><Button label="Питание и предпочтения" onPress={() => ask("Хочу скорректировать питание. Используй сохранённую цель, последний вес, предпочтения и подтверждённые записи. Уточни, что именно изменить, и запроси подтверждение.")} /><Button label="План тренировок" onPress={() => go("workouts")} /><Button label="Мою готовую схему курса" onPress={() => c.setEditor({ page: "plan" })} /><Button label="Самочувствие" onPress={() => c.setEditor({ page: "wellbeing" })} /><Button label="Написать в поддержку" onPress={() => router.push({ pathname: "/chat", params: { mode: "support" } })} /></> : null}
    </View>
}

function MealCopy({ entry }: { entry: CompanionEntry }) {
    return <><Copy heading>{entry.data.name || "Приём пищи"}</Copy>{entry.data.nutrition ? <Copy>{entry.data.nutrition.kcal} ккал · Б {entry.data.nutrition.protein} · Ж {entry.data.nutrition.fat} · У {entry.data.nutrition.carbs} г</Copy> : null}{entry.data.estimated ? <Copy muted>Оценка: {entry.data.assumptions || "порция и состав требуют проверки"}</Copy> : null}</>
}
function MeasurementEditor({ controller: c, save, onClose }: { controller: Controller; save: (action: CompanionAction) => Promise<void>; onClose: () => void }) {
    const [measurement, setMeasurement] = useState<Measurement>({})
    const original = useRef(new Date().toISOString())
    const [date, setDate] = useState(localDateTime(original.current))
    return <View style={styles.section}><Field label="Дата и время, ГГГГ-ММ-ДД ЧЧ:ММ" value={date} onChange={setDate} />{(Object.keys(measurementLabels) as (keyof Measurement)[]).map(key => <Field key={key} label={measurementLabels[key]} numeric value={measurement[key]} onChange={text => setMeasurement({ ...measurement, [key]: text.trim() ? text.replace(",", ".") : null })} />)}<Button label="Подтвердить замеры" primary disabled={c.busy || !Object.values(measurement).some(value => value != null) || Object.values(measurement).some(value => value != null && (numeric(value) == null || Number(value) <= 0))} onPress={() => void c.attempt(async () => { const entry: EntryData = { kind: "measurement", occurred_at: localEntryTimestamp(date, original.current), measurement }; await save({ kind: "entry", entry }); onClose() })} /><Button label="Отмена" onPress={onClose} /></View>
}

function MentorCourse({ controller: c }: { controller: Controller }) {
    const router = useRouter()
    const [date, setDate] = useState(c.state?.mentor?.today.date ?? companionCalendarDay(new Date().toISOString(), c.clock))
    const [month, setMonth] = useState(date.slice(0, 7))
    const [events, setEvents] = useState<CompanionEvent[]>([])
    const [loading, setLoading] = useState(false)
    const sequence = useRef(0)
    const invalidateLoads = useCallback(() => { sequence.current++ }, [])
    const ref = useRef(c); ref.current = c
    const keys = useRef(new Map<string, string>())
    const load = useCallback(async () => {
        const token = ++sequence.current; setLoading(true)
        const [year, number] = month.split("-").map(Number)
        const next = localDateTime(new Date(year, number, 1)).slice(0, 10)
        try { const result = await getCompanionEvents(`${month}-01`, next); if (sequence.current === token) setEvents(result.events) }
        finally { if (sequence.current === token) setLoading(false) }
    }, [month])
    useEffect(() => { void ref.current.attempt(load); return invalidateLoads }, [load, c.clock, invalidateLoads])
    const localDay = (event: CompanionEvent) => companionCalendarDay(event.scheduled_at, c.clock)
    const markedDates = Object.fromEntries(events.map(event => [localDay(event), { marked: true }]))
    const plan = c.state?.plan
    return <><Copy heading>Мой курс</Copy><Copy muted>Только ваша готовая схема. Изменения назначений обсуждаются со специалистом.</Copy>
        {plan ? <><Copy heading>{plan.data.name}</Copy><Copy>{plan.status === "active" ? "Активен" : plan.status === "paused" ? "На паузе" : "Завершён"}</Copy>{plan.data.items.map((item, index) => <View key={index} style={styles.section}><Copy>{item.name}</Copy>{item.stages.map((stage, i) => <Copy key={i}>{stage.start_date} – {stage.end_date} · {stage.amount} {stage.unit} · {stage.times.join(", ")}</Copy>)}</View>)}</> : <Copy muted>Готовая схема пока не сохранена.</Copy>}
        <Button label={plan ? "Обновить мою схему" : "Записать готовую схему"} onPress={() => c.setEditor({ page: "plan" })} />
        {plan?.status === "active" ? <Button label="Приостановить напоминания курса" disabled={c.busy} onPress={() => void c.attempt(async () => { await c.perform({ kind: "plan_status", expected_version: c.state?.profile?.version, status: "paused" }); await load() })} /> : null}
        {plan && plan.status !== "completed" ? <Button label="Завершить учёт курса" disabled={c.busy} onPress={() => Alert.alert("Завершить учёт курса?", "Будущие напоминания будут отменены. История сохранится.", [{ text: "Отмена", style: "cancel" }, { text: "Завершить", onPress: () => void c.attempt(async () => { await c.perform({ kind: "plan_status", expected_version: c.state?.profile?.version, status: "completed" }); await load() }) }])} /> : null}
        <Calendar current={`${month}-01`} onDayPress={day => setDate(day.dateString)} onMonthChange={value => setMonth(value.dateString.slice(0, 7))} markedDates={{ ...markedDates, [date]: { ...markedDates[date], selected: true, selectedColor: "#176B4A" } }} firstDay={1} />
        {loading ? <ActivityIndicator /> : null}<Copy heading>{date}</Copy>
        {events.filter(event => localDay(event) === date).map(event => <View key={event.id} style={styles.section}><Copy>{event.data.name} · {event.data.amount} {event.data.unit}</Copy><Copy muted>{formatCompanionDate(event.scheduled_at, c.clock)} · {event.status === "done" ? "Выполнено" : event.status === "skipped" ? "Пропущено" : "Без отметки"}</Copy><View style={styles.row}>{(["done", "skipped", "pending"] as const).filter(status => status !== event.status).map(status => <Button key={status} label={status === "done" ? "Отметить" : status === "skipped" ? "Пропущено" : "Снять отметку"} disabled={c.busy || status === "done" && Date.parse(event.scheduled_at) > Date.now()} onPress={() => void c.attempt(async () => { const identity = `${event.id}:${event.version}:${status}`; const key = keys.current.get(identity) ?? requestKey(); keys.current.set(identity, key); await c.perform({ kind: "event", resource_id: event.id, expected_version: event.version, request_key: key, status }); keys.current.delete(identity); await load() })} />)}</View></View>)}
        {!loading && !events.some(event => localDay(event) === date) ? <Copy muted>На этот день нет событий.</Copy> : null}
        {events.length >= 200 ? <Copy muted>Показаны первые 200 событий. Полную историю можно открыть отдельно.</Copy> : null}
        {Platform.OS !== "ios" ? <Button label="Запас по моей схеме" onPress={() => c.setEditor({ page: "supply" })} /> : plan ? <View style={styles.section}><Copy heading>Домашний запас</Copy>{plan.data.items.map((item, index) => <Copy key={index}>{item.name}: {item.home_amount ?? "не указан"} {item.package_unit ?? ""} на момент сохранения схемы</Copy>)}</View> : null}<Button label="Самочувствие" onPress={() => c.setEditor({ page: "wellbeing" })} /><Button label="История событий" onPress={() => c.setEditor({ page: "events" })} /><Copy muted>Контакт врача пока не настроен.</Copy><Button label="Написать в поддержку" onPress={() => router.push({ pathname: "/chat", params: { mode: "support" } })} />
    </>
}
