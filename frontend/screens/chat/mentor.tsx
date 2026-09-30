import { useCallback, useEffect, useRef, useState } from "react"
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, useWindowDimensions, View } from "react-native"
import { Calendar, LocaleConfig } from "react-native-calendars"
import { useRouter } from "expo-router"
import { useTheme } from "@/providers/theme-provider"
import { ProfileIcon, SavedIcon } from "@/components/footer/sticky-footer.icons"
import CameraIcon from "@/assets/icons/chat/camera-svgrepo-com.svg"
import MicrophoneIcon from "@/assets/icons/chat/microphone-alt-svgrepo-com.svg"
import { companionDialogue, getCompanionEntries, getCompanionEvents, getCompanionFavoriteMeals, getCompanionSummary, requestKey } from "@/services/api/companion"
import type { CompanionAction, CompanionEntry, CompanionEvent, EntryData, Measurement, MentorDashboard, Summary } from "@/services/api/companion"
import type { AIAttachmentRead, AIMessageRead } from "@/services/api/ai-chat.types"
import type { useCompanion } from "@/screens/chat/companion"
import { calendarDate, companionCalendarDay, formatCompanionDate, localDateTime, localEntryTimestamp } from "@/screens/chat/companion-timezones"
import { goalLabels, measurementLabels, numeric, repeatMeal } from "@/screens/chat/mentor-data"
import type { MentorPage } from "@/screens/chat/mentor-data"
import { MentorWorkouts } from "@/screens/chat/mentor-workouts"
import { MentorProgress } from "@/screens/chat/mentor-progress"
import { MentorPhotos } from "@/screens/chat/mentor-photos"
import { MentorButton as Button, MentorField as Field, MentorTabs as Tabs, MentorText as Copy, mentorStyles as styles, MentorIcon, useMentorPalette } from "@/screens/chat/mentor-ui"

LocaleConfig.locales["mentor-ru"] = {
    monthNames: ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"],
    monthNamesShort: ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"],
    dayNames: ["Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"],
    dayNamesShort: ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"], today: "Сегодня",
}
LocaleConfig.defaultLocale = "mentor-ru"

type Controller = ReturnType<typeof useCompanion>
export type MentorComposeMode = "text" | "photo" | "voice"
export const mentorNavigation = { today: "Сегодня", nutrition: "Питание", workouts: "Тренировки", course: "Мой курс", more: "Ещё" } as const
export function MentorNavigation({ controller: c }: { controller: Controller }) {
    const colors = useMentorPalette()
    const icons = { today: "calendar", nutrition: "food", workouts: "workout", course: "book", more: "more" } as const
    return <ScrollView horizontal showsHorizontalScrollIndicator={false} keyboardShouldPersistTaps="handled" contentContainerStyle={styles.navigation}>
        <View accessibilityRole="tablist" style={{ flexDirection: "row", gap: 4 }}>{(Object.keys(mentorNavigation) as (keyof typeof mentorNavigation)[]).map(page => <Pressable key={page} accessibilityRole="tab" accessibilityState={{ selected: c.mentorPage === page }} accessibilityLabel={mentorNavigation[page]} onPress={() => { c.setEditor(null); c.setMentorPage(page) }} style={({ pressed }) => [styles.navigationPill, { backgroundColor: colors.surface, opacity: pressed ? 0.7 : 1 }]}><MentorIcon name={icons[page]} size={14} color={colors.blue} /><Text style={[styles.navigationText, { color: colors.blue }]}>{mentorNavigation[page]}</Text></Pressable>)}</View>
    </ScrollView>
}

export function MentorWorkspace({ controller: c, onCompose, onPrompt, displayName, photoMessages = [], renderPhotoAttachments = () => null }: { controller: Controller; displayName?: string | null; onCompose: (mode: MentorComposeMode, text: string) => void; onPrompt: (text: string) => Promise<unknown>; photoMessages?: AIMessageRead[]; renderPhotoAttachments?: (attachments: AIAttachmentRead[]) => React.ReactNode }) {
    const { palette } = useTheme()
    const colors = useMentorPalette()
    const { width: screenWidth } = useWindowDimensions()
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
    const report = (period: 7 | 30) => void c.attempt(async () => { await companionDialogue("progress", period); c.setMentorPage(null); await onPrompt("") })
    const mentor = c.state?.mentor
    const latest = mentor?.latest_weight
    const nutrition = mentor?.today.nutrition
    const tasks = mentor?.today.tasks ?? []
    const sortedEntries = [...entries].sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at))
    const meals = mealMode === "favorites" ? favorites : sortedEntries.filter(entry => entry.kind === "meal")
    const periodEntries = progressEntries.filter(entry => Date.parse(entry.occurred_at) <= Date.now())
    const workoutTask = tasks.find(task => task.kind === "workout" && task.status !== "done") ?? tasks.find(task => task.kind === "workout")
    const courseTask = tasks.find(task => task.kind === "course" && task.status === "pending")
    const localTime = (date: string) => formatCompanionDate(date, c.clock).match(/(\d{2}:\d{2})(?::\d{2})?/)?.[1] ?? ""
    const numberLabel = (value: unknown) => numeric(value)?.toLocaleString("ru-RU", { maximumFractionDigits: 1 }) ?? "—"
    const page = c.mentorPage
    if (!page) return null
    return <View testID="mentor-workspace" style={[styles.body, { backgroundColor: colors.surface }, page === "today" ? { gap: 12, padding: 14 } : null]}>
        <View style={styles.header}>
            {page !== "today" ? <Pressable accessibilityRole="button" accessibilityLabel="Назад к сегодняшнему плану" onPress={() => go("today")} hitSlop={8} style={{ minHeight: 36, justifyContent: "center" }}><MentorIcon name="back" size={18} color={colors.green} /></Pressable> : null}
            <View style={[styles.avatar, { backgroundColor: colors.mint }]}><MentorIcon name="leaf" size={26} /></View>
            <Text style={[styles.heading, { color: colors.green, fontSize: screenWidth < 360 ? 14 : 16 }]}>Наставник ElixirPeptide</Text>
            {page === "today" ? <Text style={[styles.time, { color: colors.muted }]}>{localTime(new Date().toISOString())}</Text> : null}
        </View>
        {c.error ? <View style={[styles.notice, { backgroundColor: colors.mint }]}><Copy>{c.error}</Copy><Button label="Обновить данные" onPress={() => void c.attempt(async () => { await c.refresh(); await load() })} /></View> : null}
        {c.busy || loading && page !== "today" ? <ActivityIndicator color={colors.green} /> : null}
        {page === "today" ? <>
            <Copy style={styles.greeting}>Добрый день{displayName?.trim() ? `, ${displayName.trim().split(" ")[0]}` : ""}!</Copy>
            <View style={styles.plan}>
                <Copy style={[styles.planLine, { fontWeight: "700", marginBottom: 2 }]}>Ваш план на сегодня:</Copy>
                <Text style={[styles.planLine, { color: colors.text }]}>🍽️ <Text style={{ fontWeight: "700" }}>Питание: </Text>{nutrition ? `${numberLabel(nutrition.consumed.kcal)}${nutrition.target ? ` из ${numberLabel(nutrition.target.kcal)}` : ""} ккал` : "пока нет записей"}</Text>
                <Text style={[styles.planLine, { color: colors.text }]}>🏋️ <Text style={{ fontWeight: "700" }}>Силовая: </Text>{workoutTask ? `${workoutTask.label}${workoutTask.scheduled_at ? ` · ${localTime(workoutTask.scheduled_at)}` : workoutTask.status === "done" ? " · выполнена" : workoutTask.status === "in_progress" ? " · в процессе" : ""}` : mentor?.workout_plan ? "день отдыха" : "план не добавлен"}</Text>
                <Text style={[styles.planLine, { color: colors.text }]}>🧬 <Text style={{ fontWeight: "700" }}>Курс: </Text>{courseTask ? `напоминание${courseTask.scheduled_at ? ` · ${localTime(courseTask.scheduled_at)}` : " сегодня"}` : c.state?.plan ? (c.state.plan.status === "paused" ? "напоминания на паузе" : c.state.plan.status === "completed" ? "завершён" : tasks.some(task => task.kind === "course" && task.status === "skipped") ? "есть пропущенные отметки" : tasks.some(task => task.kind === "course" && task.status === "done") ? "выполнено" : "сегодня без напоминаний") : "не добавлен"}</Text>
                <Text style={[styles.planLine, { color: colors.text }]}>⚖️ <Text style={{ fontWeight: "700" }}>Вес: </Text>{latest ? `${numberLabel(latest.data.weight_kg)} кг` : "ещё не записан"}{c.state?.profile?.data.target_weight_kg ? ` · цель ${numberLabel(c.state.profile.data.target_weight_kg)} кг` : ""}</Text>
            </View>
            {!nutrition?.target ? <Pressable accessibilityRole="button" accessibilityLabel="Дополнить профиль" onPress={() => c.setEditor({ page: "profile" })} style={[styles.notice, { backgroundColor: colors.mint }]}><Copy style={{ color: colors.green }}>Дополните профиль, чтобы рассчитать ваш план →</Copy></Pressable> : null}
            {tasks.length ? <Copy style={{ fontSize: 17 }}>Выполнено {tasks.filter(task => task.status === "done").length} из {tasks.length}</Copy> : <Copy muted>На сегодня нет запланированных событий.</Copy>}
            <View style={styles.actions}>
                <Button label="Добавить еду" icon={<MentorIcon name="plus" size={24} color="#FFFFFF" />} primary onPress={() => { setAddFood(true); c.setMentorPage("nutrition") }} />
                <View style={styles.actionRow}><View style={styles.actionCell}><Button compact label="Начать тренировку" icon={<MentorIcon name="workout" size={20} color={colors.green} />} onPress={() => go("workouts")} /></View><View style={styles.actionCell}><Button compact label="Открыть курс" icon={<MentorIcon name="book" size={20} color={colors.green} />} onPress={() => go("course")} /></View></View>
                <View style={styles.actionRow}><View style={styles.actionCell}><Button compact label="Самочувствие" icon={<MentorIcon name="smile" color={colors.green} />} onPress={() => c.setEditor({ page: "wellbeing" })} /></View><View style={styles.actionCell}><Button compact label="Прогресс" icon={<MentorIcon name="progress" color={colors.green} />} onPress={() => go("progress")} /></View></View>
                <Button label="Скорректировать план" icon={<MentorIcon name="adjust" color={colors.green} />} onPress={() => go("adjust")} />
            </View>
        </> : null}
        {page === "nutrition" ? <>
            <Copy heading>Питание</Copy>
            {nutrition ? <NutritionOverview nutrition={nutrition} /> : <Copy muted>Запишите первый приём пищи, чтобы увидеть итоги дня.</Copy>}
            {nutrition && !nutrition.target ? <Button label="Задать ориентиры питания" onPress={() => c.setEditor({ page: "nutrition" })} /> : null}
            <Button label="Добавить еду" primary onPress={() => setAddFood(value => !value)} />
            {addFood ? <View style={[styles.notice, { backgroundColor: colors.mint }]}><Copy>Отправьте фотографию еды, голосовое сообщение или напишите, что вы съели.</Copy><Copy muted>Например: «гречка 150 г, куриная грудка 200 г и овощной салат».</Copy><Button label="Фото еды" icon={<CameraIcon width={22} height={22} color={palette.text} />} onPress={() => compose("photo", "Хочу записать еду по фото. Уточни порцию и предложи запись для подтверждения.")} /><Button label="Рассказать голосом" icon={<MicrophoneIcon width={22} height={22} color={palette.text} />} onPress={() => compose("voice", "")} /><Button label="Написать о еде" onPress={() => compose("text", "Хочу записать еду: ")} /><Button label="Внести КБЖУ вручную" onPress={() => c.setEditor({ page: "meal" })} /></View> : null}
            <View style={styles.actionRow}><View style={styles.actionCell}><Button label="Что мне поесть?" icon={<MentorIcon name="food" color={colors.green} />} onPress={() => ask("Что мне поесть? Учти подтверждённые приёмы пищи за сегодня, оставшиеся калории и белок, мои любимые блюда, предпочтения и ограничения.")} /></View><View style={styles.actionCell}><Button label="Найти продукт" icon={<MentorIcon name="search" color={colors.green} />} onPress={() => compose("text", "Хочу найти продукт: ")} /></View></View>
            <Tabs items={{ recent: "Недавние", favorites: "Избранное", history: "История" }} value={mealMode} onChange={setMealMode} />
            {mealMode === "history" ? <View style={styles.row}><Field label="С даты, ГГГГ-ММ-ДД" value={historyFrom} onChange={setHistoryFrom} /><Field label="До даты (не включая)" value={historyTo} onChange={setHistoryTo} /><Button label="Загрузить историю" disabled={loading} onPress={() => setHistoryRange({ from: historyFrom, to: historyTo })} /></View> : null}
            {repeating ? <View style={styles.section}><Copy heading>Повторить приём пищи?</Copy><MealCopy entry={repeating} /><Button label="Подтвердить на сейчас" primary disabled={c.busy} onPress={() => void c.attempt(async () => { await save({ kind: "entry", entry: repeatMeal(repeating, repeating.data.occurred_at) }); setRepeating(null) })} /><Button label="Исправить перед записью" onPress={() => { c.setEditor({ page: "meal", proposal: { kind: "entry", summary: "", entry: repeatMeal(repeating, repeating.data.occurred_at) } }); setRepeating(null) }} /><Button label="Отмена" onPress={() => setRepeating(null)} /></View> : null}
            {!meals.length ? <Copy muted>{mealMode === "favorites" ? "Пока нет избранных блюд." : "В выбранном периоде нет записей о еде."}</Copy> : meals.slice(0, mealMode === "recent" ? 8 : 200).map(entry => <View key={entry.id} style={styles.section}><MealCopy entry={entry} /><Copy muted>{formatCompanionDate(entry.occurred_at, c.clock)}</Copy><View style={styles.row}><Button label="Повторить" disabled={c.busy} onPress={() => setRepeating({ ...entry, data: repeatMeal(entry) })} /><Pressable accessibilityRole="button" accessibilityLabel={entry.data.favorite ? "Убрать из избранного" : "В избранное"} accessibilityState={{ selected: !!entry.data.favorite }} disabled={c.busy} onPress={() => void c.attempt(() => save({ kind: "entry", resource_id: entry.id, expected_version: entry.version, entry: { ...entry.data, favorite: !entry.data.favorite } }))} style={{ padding: 12 }}><SavedIcon color={entry.data.favorite ? "#C34768" : palette.mutedText} /></Pressable><Button label="Исправить" onPress={() => c.setEditor({ page: "meal", entry })} /></View></View>)}
            {mealMode === "favorites" && moreFavorites ? <Copy muted>Показаны последние 200 избранных записей.</Copy> : null}
            {entries.length >= 200 ? <Copy muted>Показаны последние 200 записей. Сузьте период истории.</Copy> : null}
        </> : null}
        {page === "workouts" ? <MentorWorkouts controller={c} entries={entries} onChanged={load} /> : null}
        {page === "course" ? <MentorCourse controller={c} /> : null}
        {page === "progress" ? <MentorProgress controller={c} entries={periodEntries} weeklyEntries={weeklyEntries} summary={summary} days={days} setDays={setDays} progressTab={progressTab} setProgressTab={setProgressTab} onReport={report}
            measurementsContent={<><Button label="Добавить замеры" primary onPress={() => setMeasurementOpen(true)} />{measurementOpen ? <MeasurementEditor controller={c} save={save} onClose={() => setMeasurementOpen(false)} /> : null}{periodEntries.filter(entry => entry.kind === "measurement").map(entry => <View key={entry.id} style={styles.section}><Copy muted>{formatCompanionDate(entry.occurred_at, c.clock)}</Copy>{Object.entries(entry.data.measurement ?? {}).filter(([, value]) => value != null).map(([key, value]) => <Copy key={key}>{measurementLabels[key as keyof Measurement]}: {value}</Copy>)}</View>)}{!periodEntries.some(entry => entry.kind === "measurement") ? <Copy muted>Замеров пока нет.</Copy> : null}</>}
            photosContent={<><Button label="Добавить фото прогресса" icon={<CameraIcon width={22} height={22} color={palette.text} />} onPress={() => compose("photo", "Фото прогресса. Не оценивай состав тела и здоровье по фотографии.")} /><MentorPhotos controller={c} days={days} messages={photoMessages} renderAttachments={renderPhotoAttachments} /></>}
        /> : null}
        {page === "more" ? <><Copy heading>Мой наставник</Copy><Copy muted>Ваши цели, история и помощь рядом.</Copy><Button label="Спросить наставника" icon={<MentorIcon name="chat" color="#FFFFFF" />} primary onPress={() => go("ask")} /><View style={styles.row}><ProfileIcon color={colors.green} /><Copy>{c.state?.profile?.data.goal ? goalLabels[c.state.profile.data.goal] : "Цель не указана"}{c.state?.profile?.data.custom_goal ? `: ${c.state.profile.data.custom_goal}` : ""}</Copy></View><Copy>Последний вес: {latest ? `${latest.data.weight_kg} кг · ${formatCompanionDate(latest.occurred_at, c.clock)}` : "не записан"}</Copy><Button label="Профиль и цели" onPress={() => c.setEditor({ page: "profile" })} /><Button label="Записать вес" onPress={() => c.setEditor({ page: "weight" })} /><Button label="Прогресс и замеры" onPress={() => go("progress")} /><Button label="Настройки и напоминания" onPress={() => c.setEditor({ page: "settings" })} /><Button label="Дневник" onPress={() => c.setEditor({ page: "journal" })} /><Button label="Написать в поддержку" onPress={() => router.push({ pathname: "/chat", params: { mode: "support" } })} /></> : null}
        {page === "ask" ? <><Copy heading>Спросить наставника</Copy><Copy muted>Выберите тему или напишите свой вопрос.</Copy>{[
            ["🍲 Что поесть?", "Что мне поесть? Учти сохранённые предпочтения, любимые блюда и остаток КБЖУ за сегодня."],
            ["📊 Проанализировать мой день", "Проанализируй мой день по сохранённым записям питания, тренировок и самочувствия."],
            ["🏋️ Скорректировать тренировку", "Помоги скорректировать тренировку с учётом моего плана и записанных результатов."],
            ["⚖️ Почему вес стоит?", "Помоги разобраться в динамике моего веса, учитывая сохранённые измерения и питание."],
        ].map(([label, prompt]) => <Button key={label} label={label} onPress={() => ask(prompt)} />)}<Button label="🧬 Вопрос по моему курсу" onPress={() => router.push({ pathname: "/chat", params: { mode: "support" } })} /><Button label="Задать свой вопрос" icon={<MentorIcon name="chat" color="#FFFFFF" />} primary onPress={() => compose("text", "")} /></> : null}
        {page === "adjust" ? <><Copy heading>Что скорректировать?</Copy><Copy muted>Выберите, что сейчас не подходит.</Copy><Button label="🍽 Не подходит питание" onPress={() => ask("Хочу скорректировать питание. Используй сохранённую цель, последний вес, предпочтения и подтверждённые записи. Уточни, что именно изменить, и запроси подтверждение.")} /><Button label="🔥 Слишком мало калорий" onPress={() => ask("Мне не хватает калорий. Проанализируй сохранённую цель, питание и самочувствие, помоги скорректировать план с подтверждением.")} /><Button label="🏋️ Не подходит тренировка" onPress={() => go("workouts")} /><Button label="📅 Неудобное расписание" onPress={() => c.setEditor({ page: "settings" })} /><Button label="🧬 Вопрос по курсу" onPress={() => router.push({ pathname: "/chat", params: { mode: "support" } })} /><Button label="😓 Сложно соблюдать план" onPress={() => ask("Мне сложно соблюдать план. Помоги выбрать посильный следующий шаг с учётом моих записей.")} /><Button label="Другая причина" onPress={() => compose("text", "Хочу скорректировать план: ")} /><Button label="Цель и профиль" onPress={() => c.setEditor({ page: "profile" })} /></> : null}
    </View>
}

function NutritionOverview({ nutrition }: { nutrition: MentorDashboard["today"]["nutrition"] }) {
    const colors = useMentorPalette()
    const fraction = (value: unknown, target: unknown) => {
        const amount = numeric(value), total = numeric(target)
        return amount != null && total != null && total > 0 ? Math.max(0, Math.min(1, amount / total)) : 0
    }
    return <View style={[styles.notice, { backgroundColor: colors.mint }]}>
        <Copy muted>Итоги за сегодня</Copy>
        <Text style={{ color: colors.green, fontSize: 30, fontWeight: "600" }}>{Number(nutrition.consumed.kcal).toLocaleString("ru-RU")} <Text style={{ fontSize: 15, fontWeight: "400", color: colors.muted }}>{nutrition.target ? `из ${Number(nutrition.target.kcal).toLocaleString("ru-RU")} ` : ""}ккал</Text></Text>
        {nutrition.target ? <View style={{ height: 7, backgroundColor: colors.surface, borderRadius: 5, overflow: "hidden" }}><View style={{ height: 7, borderRadius: 5, width: `${fraction(nutrition.consumed.kcal, nutrition.target.kcal) * 100}%`, backgroundColor: colors.greenBright }} /></View> : null}
        <View style={styles.row}>{(["protein", "fat", "carbs"] as const).map((key, index) => <View key={key} style={{ flex: 1, gap: 4, paddingTop: 8 }}><Copy muted style={{ fontSize: 12 }}>{["Белки", "Жиры", "Углеводы"][index]}</Copy><Copy style={{ fontSize: 16, fontWeight: "600", color: colors.green }}>{nutrition.consumed[key]} г</Copy>{nutrition.target ? <Copy muted style={{ fontSize: 12 }}>из {nutrition.target[key]} г</Copy> : null}</View>)}</View>
        {nutrition.remaining ? <Copy style={{ color: colors.green }}>Осталось {nutrition.remaining.kcal} ккал · {nutrition.remaining.protein} г белка</Copy> : null}
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
    const colors = useMentorPalette()
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
        <Calendar theme={{ backgroundColor: colors.soft, calendarBackground: colors.soft, dayTextColor: colors.text, monthTextColor: colors.green, arrowColor: colors.green, todayTextColor: colors.green, textDisabledColor: colors.muted, textSectionTitleColor: colors.muted, selectedDayBackgroundColor: colors.greenBright, selectedDayTextColor: "#FFFFFF", dotColor: colors.greenBright }} style={{ borderRadius: 18, padding: 8 }} current={`${month}-01`} onDayPress={day => setDate(day.dateString)} onMonthChange={value => setMonth(value.dateString.slice(0, 7))} markedDates={{ ...markedDates, [date]: { ...markedDates[date], selected: true, selectedColor: "#176B4A" } }} firstDay={1} />
        {loading ? <ActivityIndicator /> : null}<Copy heading>{date}</Copy>
        {events.filter(event => localDay(event) === date).map(event => <View key={event.id} style={styles.section}><Copy>{event.data.name} · {event.data.amount} {event.data.unit}</Copy><Copy muted>{formatCompanionDate(event.scheduled_at, c.clock)} · {event.status === "done" ? "Выполнено" : event.status === "skipped" ? "Пропущено" : "Без отметки"}</Copy><View style={styles.row}>{(["done", "skipped", "pending"] as const).filter(status => status !== event.status).map(status => <Button key={status} label={status === "done" ? "Отметить" : status === "skipped" ? "Пропущено" : "Снять отметку"} disabled={c.busy || status === "done" && Date.parse(event.scheduled_at) > Date.now()} onPress={() => void c.attempt(async () => { const identity = `${event.id}:${event.version}:${status}`; const key = keys.current.get(identity) ?? requestKey(); keys.current.set(identity, key); await c.perform({ kind: "event", resource_id: event.id, expected_version: event.version, request_key: key, status }); keys.current.delete(identity); await load() })} />)}</View></View>)}
        {!loading && !events.some(event => localDay(event) === date) ? <Copy muted>На этот день нет событий.</Copy> : null}
        {events.length >= 200 ? <Copy muted>Показаны первые 200 событий. Полную историю можно открыть отдельно.</Copy> : null}
        <Button label="Изменить время напоминаний" icon={<MentorIcon name="clock" color={colors.green} />} onPress={() => c.setEditor({ page: "settings" })} /><Button label="Запас по моей схеме" onPress={() => c.setEditor({ page: "supply" })} /><Button label="Самочувствие" onPress={() => c.setEditor({ page: "wellbeing" })} /><Button label="История событий" onPress={() => c.setEditor({ page: "events" })} /><Copy muted>Контакт врача пока не настроен.</Copy><Button label="Написать в поддержку" onPress={() => router.push({ pathname: "/chat", params: { mode: "support" } })} />
    </>
}
