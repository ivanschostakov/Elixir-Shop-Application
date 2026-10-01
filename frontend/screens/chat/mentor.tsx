import { mentorText as mt, mentorLocale } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { QuietLoading } from "@/components/ui/quiet-loading"
import { useCallback, useEffect, useRef, useState } from "react"
import { ActivityIndicator, Alert, Pressable, Text, useWindowDimensions, View } from "react-native"
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
import { goalLabels, measurementLabels, mentorUnitLabel, numeric, repeatMeal } from "@/screens/chat/mentor-data"
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
for (const language of ["en", "kz"] as const) {
    const source = LocaleConfig.locales["mentor-ru"]
    LocaleConfig.locales[`mentor-${language}`] = {
        monthNames: source.monthNames.map((label: string) => mt(label, [], language)),
        monthNamesShort: source.monthNamesShort.map((label: string) => mt(label, [], language)),
        dayNames: source.dayNames.map((label: string) => mt(label, [], language)),
        dayNamesShort: source.dayNamesShort.map((label: string) => mt(label, [], language)),
        today: mt("Сегодня", [], language),
    }
}

type Controller = ReturnType<typeof useCompanion>
export type MentorComposeMode = "text" | "photo" | "voice"
export const mentorNavigation = { get today() { return mt("Сегодня") }, get nutrition() { return mt("Питание") }, get workouts() { return mt("Тренировки") }, get course() { return mt("Мой курс") }, get more() { return mt("Ещё") } } as const
export function MentorNavigation({ controller: c }: { controller: Controller }) {
    useLanguage()
    const colors = useMentorPalette()
    const icons = { today: "calendar", nutrition: "food", workouts: "workout", course: "book", more: "more" } as const
    return <View accessibilityRole="tablist" style={styles.navigation}>
        {(Object.keys(mentorNavigation) as (keyof typeof mentorNavigation)[]).map(page => <Pressable key={page} accessibilityRole="tab" accessibilityState={{ selected: c.mentorPage === page }} accessibilityLabel={mentorNavigation[page]} onPress={() => { c.setEditor(null); c.setMentorPage(page) }} style={({ pressed }) => [styles.navigationPill, { backgroundColor: c.mentorPage === page ? colors.mint : colors.surface, opacity: pressed ? 0.7 : 1 }]}><MentorIcon name={icons[page]} size={28} color={colors.blue} /></Pressable>)}
    </View>
}

export function MentorWorkspace({ controller: c, onCompose, onPrompt, displayName, photoMessages = [], renderPhotoAttachments = () => null }: { controller: Controller; displayName?: string | null; onCompose: (mode: MentorComposeMode, text: string) => void; onPrompt: (text: string) => Promise<unknown>; photoMessages?: AIMessageRead[]; renderPhotoAttachments?: (attachments: AIAttachmentRead[]) => React.ReactNode }) {
    useLanguage()
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
    const [progressSnapshots, setProgressSnapshots] = useState<Record<string, { summary: Summary; entries: CompanionEntry[]; weekly: CompanionEntry[] }>>({})
    const [historyFrom, setHistoryFrom] = useState(calendarDate(-29))
    const [historyTo, setHistoryTo] = useState(calendarDate(1))
    const [historyRange, setHistoryRange] = useState({ from: calendarDate(-29), to: calendarDate(1) })
    const progressKind = progressTab === "workouts" ? "workout" : progressTab === "measurements" ? "measurement" : "weight"
    const progressKey = `${days}|${progressKind}|${c.clock}`
    const progressSnapshot = progressSnapshots[progressKey]
    const summary = progressSnapshot?.summary ?? null
    const progressEntries = progressSnapshot?.entries ?? []
    const weeklyEntries = progressSnapshot?.weekly ?? []
    const sequence = useRef(0)
    const invalidateLoads = useCallback(() => { sequence.current++ }, [])
    const keys = useRef(new Map<string, string>())
    const callbacks = useRef(c); callbacks.current = c
    const load = useCallback(async () => {
        if (c.mentorPage !== "nutrition" && c.mentorPage !== "workouts") return
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
        void getCompanionFavoriteMeals().then(result => { if (!cancelled) { setFavorites(result.entries); setMoreFavorites(result.may_have_more) } }).catch(error => { if (!cancelled) callbacks.current.setError(error instanceof Error ? error.message : mt("Не удалось загрузить избранное")) })
        return () => { cancelled = true }
    }, [mealMode, c.mentorPage, c.state])
    useEffect(() => {
        if (c.mentorPage !== "progress") return
        let cancelled = false
        // Commit one complete report; keep the previous snapshot during background refreshes.
        void Promise.all([
            getCompanionEntries(calendarDate(-6), calendarDate(1), "weight"),
            getCompanionEntries(calendarDate(1 - days), calendarDate(1), progressKind),
            getCompanionSummary(calendarDate(1 - days), calendarDate(1)),
        ]).then(([weekly, period, nextSummary]) => {
            if (!cancelled) setProgressSnapshots(previous => ({ ...previous, [progressKey]: {
                summary: nextSummary, entries: period.entries,
                weekly: weekly.entries.filter(entry => Date.parse(entry.occurred_at) <= Date.now()),
            } }))
        }).catch(error => { if (!cancelled) callbacks.current.setError(error instanceof Error ? error.message : mt("Не удалось загрузить отчёт")) })
        return () => { cancelled = true }
    }, [days, c.mentorPage, c.clock, c.state, progressKey, progressKind])
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
    const numberLabel = (value: unknown) => numeric(value)?.toLocaleString(mentorLocale(), { maximumFractionDigits: 1 }) ?? "—"
    const page = c.mentorPage
    if (!page) return null
    return <View testID="mentor-workspace" style={[styles.body, { backgroundColor: colors.surface }, page === "today" ? { gap: 12, padding: 14 } : null]}>
        <View style={styles.header}>
            {page !== "today" ? <Pressable accessibilityRole="button" accessibilityLabel={mt("Назад к сегодняшнему плану")} onPress={() => go("today")} hitSlop={8} style={{ minHeight: 36, justifyContent: "center" }}><MentorIcon name="back" size={18} color={colors.green} /></Pressable> : null}
            <View style={[styles.avatar, { backgroundColor: colors.mint }]}><MentorIcon name="leaf" size={26} /></View>
            <Text style={[styles.heading, { color: colors.green, fontSize: screenWidth < 360 ? 14 : 16 }]}>{mt("Наставник ElixirPeptide")}</Text>
            {page === "today" ? <Text style={[styles.time, { color: colors.muted }]}>{localTime(new Date().toISOString())}</Text> : null}
        </View>
        {c.error ? <View style={[styles.notice, { backgroundColor: colors.mint }]}><Copy>{c.error}</Copy><Button label={mt("Обновить данные")} onPress={() => void c.attempt(async () => { await c.refresh(); await load() })} /></View> : null}
        <QuietLoading loading={loading && !entries.length && (page === "nutrition" || page === "workouts")} />
        {page === "today" ? <>
            <Copy style={styles.greeting}>{mt("Добрый день")}{displayName?.trim() ? `, ${displayName.trim().split(" ")[0]}` : ""}!</Copy>
            <View style={styles.plan}>
                <Copy style={[styles.planLine, { fontWeight: "700", marginBottom: 2 }]}>{mt("Ваш план на сегодня:")}</Copy>
                <Text style={[styles.planLine, { color: colors.text }]}>🍽️ <Text style={{ fontWeight: "700" }}>{mt("Питание: ")}</Text>{nutrition ? mt("{0}{1} ккал", [numberLabel(nutrition.consumed.kcal), nutrition.target ? mt(" из {0}", [numberLabel(nutrition.target.kcal)]) : ""]) : mt("пока нет записей")}</Text>
                <Text style={[styles.planLine, { color: colors.text }]}>🏋️ <Text style={{ fontWeight: "700" }}>{mt("Силовая: ")}</Text>{workoutTask ? `${workoutTask.label}${workoutTask.scheduled_at ? ` · ${localTime(workoutTask.scheduled_at)}` : workoutTask.status === "done" ? mt(" · выполнена") : workoutTask.status === "in_progress" ? mt(" · в процессе") : ""}` : mentor?.workout_plan ? mt("день отдыха") : mt("план не добавлен")}</Text>
                <Text style={[styles.planLine, { color: colors.text }]}>🧬 <Text style={{ fontWeight: "700" }}>{mt("Курс: ")}</Text>{courseTask ? mt("напоминание{0}", [courseTask.scheduled_at ? ` · ${localTime(courseTask.scheduled_at)}` : mt(" сегодня")]) : c.state?.plan ? (c.state.plan.status === "paused" ? mt("напоминания на паузе") : c.state.plan.status === "completed" ? mt("завершён") : tasks.some(task => task.kind === "course" && task.status === "skipped") ? mt("есть пропущенные отметки") : tasks.some(task => task.kind === "course" && task.status === "done") ? mt("выполнено") : mt("сегодня без напоминаний")) : mt("не добавлен")}</Text>
                <Text style={[styles.planLine, { color: colors.text }]}>⚖️ <Text style={{ fontWeight: "700" }}>{mt("Вес: ")}</Text>{latest ? mt("{0} кг", [numberLabel(latest.data.weight_kg)]) : mt("ещё не записан")}{c.state?.profile?.data.target_weight_kg ? mt(" · цель {0} кг", [numberLabel(c.state.profile.data.target_weight_kg)]) : ""}</Text>
            </View>
            {!nutrition?.target ? <Pressable accessibilityRole="button" accessibilityLabel={mt("Дополнить профиль")} onPress={() => c.setEditor({ page: "profile" })} style={[styles.notice, { backgroundColor: colors.mint }]}><Copy style={{ color: colors.green }}>{mt("Дополните профиль, чтобы рассчитать ваш план →")}</Copy></Pressable> : null}
            {tasks.length ? <Copy style={{ fontSize: 17 }}>{mt("Выполнено {0} из {1}", [tasks.filter(task => task.status === "done").length, tasks.length])}</Copy> : <Copy muted>{mt("На сегодня нет запланированных событий.")}</Copy>}
            <View style={styles.actions}>
                <Button label={mt("Добавить еду")} icon={<MentorIcon name="plus" size={24} color="#FFFFFF" />} primary onPress={() => { setAddFood(true); c.setMentorPage("nutrition") }} />
                <View style={styles.actionRow}><View style={styles.actionCell}><Button compact label={mt("Начать тренировку")} icon={<MentorIcon name="workout" size={20} color={colors.green} />} onPress={() => go("workouts")} /></View><View style={styles.actionCell}><Button compact label={mt("Открыть курс")} icon={<MentorIcon name="book" size={20} color={colors.green} />} onPress={() => go("course")} /></View></View>
                <View style={styles.actionRow}><View style={styles.actionCell}><Button compact label={mt("Самочувствие")} icon={<MentorIcon name="smile" color={colors.green} />} onPress={() => c.setEditor({ page: "wellbeing" })} /></View><View style={styles.actionCell}><Button compact label={mt("Прогресс")} icon={<MentorIcon name="progress" color={colors.green} />} onPress={() => go("progress")} /></View></View>
                <Button label={mt("Скорректировать план")} icon={<MentorIcon name="adjust" color={colors.green} />} onPress={() => go("adjust")} />
            </View>
        </> : null}
        {page === "nutrition" ? <>
            <Copy heading>{mt("Питание")}</Copy>
            {nutrition ? <NutritionOverview nutrition={nutrition} /> : <Copy muted>{mt("Запишите первый приём пищи, чтобы увидеть итоги дня.")}</Copy>}
            {nutrition && !nutrition.target ? <Button label={mt("Задать ориентиры питания")} onPress={() => c.setEditor({ page: "nutrition" })} /> : null}
            <Button label={mt("Добавить еду")} primary onPress={() => setAddFood(value => !value)} />
            {addFood ? <View style={[styles.notice, { backgroundColor: colors.mint }]}><Copy>{mt("Отправьте фотографию еды, голосовое сообщение или напишите, что вы съели.")}</Copy><Copy muted>{mt("Например: «гречка 150 г, куриная грудка 200 г и овощной салат».")}</Copy><Button label={mt("Фото еды")} icon={<CameraIcon width={22} height={22} color={palette.text} />} onPress={() => compose("photo", mt("Хочу записать еду по фото. Уточни порцию и предложи запись для подтверждения."))} /><Button label={mt("Рассказать голосом")} icon={<MicrophoneIcon width={22} height={22} color={palette.text} />} onPress={() => compose("voice", "")} /><Button label={mt("Написать о еде")} onPress={() => compose("text", mt("Хочу записать еду: "))} /><Button label={mt("Внести КБЖУ вручную")} onPress={() => c.setEditor({ page: "meal" })} /></View> : null}
            <View style={styles.actionRow}><View style={styles.actionCell}><Button label={mt("Что мне поесть?")} icon={<MentorIcon name="food" color={colors.green} />} onPress={() => ask(mt("Что мне поесть? Учти подтверждённые приёмы пищи за сегодня, оставшиеся калории и белок, мои любимые блюда, предпочтения и ограничения."))} /></View><View style={styles.actionCell}><Button label={mt("Найти продукт")} icon={<MentorIcon name="search" color={colors.green} />} onPress={() => compose("text", mt("Хочу найти продукт: "))} /></View></View>
            <Tabs items={{ recent: mt("Недавние"), favorites: mt("Избранное"), history: mt("История") }} value={mealMode} onChange={setMealMode} />
            {mealMode === "history" ? <View style={styles.row}><Field label={mt("С даты, ГГГГ-ММ-ДД")} value={historyFrom} onChange={setHistoryFrom} /><Field label={mt("До даты (не включая)")} value={historyTo} onChange={setHistoryTo} /><Button label={mt("Загрузить историю")} disabled={loading} onPress={() => setHistoryRange({ from: historyFrom, to: historyTo })} /></View> : null}
            {repeating ? <View style={styles.section}><Copy heading>{mt("Повторить приём пищи?")}</Copy><MealCopy entry={repeating} /><Button label={mt("Подтвердить на сейчас")} primary disabled={c.busy} onPress={() => void c.attempt(async () => { await save({ kind: "entry", entry: repeatMeal(repeating, repeating.data.occurred_at) }); setRepeating(null) })} /><Button label={mt("Исправить перед записью")} onPress={() => { c.setEditor({ page: "meal", proposal: { kind: "entry", summary: "", entry: repeatMeal(repeating, repeating.data.occurred_at) } }); setRepeating(null) }} /><Button label={mt("Отмена")} onPress={() => setRepeating(null)} /></View> : null}
            {!meals.length ? <Copy muted>{mealMode === "favorites" ? mt("Пока нет избранных блюд.") : mt("В выбранном периоде нет записей о еде.")}</Copy> : meals.slice(0, mealMode === "recent" ? 8 : 200).map(entry => <View key={entry.id} style={styles.section}><MealCopy entry={entry} /><Copy muted>{formatCompanionDate(entry.occurred_at, c.clock)}</Copy><View style={styles.row}><Button label={mt("Повторить")} disabled={c.busy} onPress={() => setRepeating({ ...entry, data: repeatMeal(entry) })} /><Pressable accessibilityRole="button" accessibilityLabel={entry.data.favorite ? mt("Убрать из избранного") : mt("В избранное")} accessibilityState={{ selected: !!entry.data.favorite }} disabled={c.busy} onPress={() => void c.attempt(() => save({ kind: "entry", resource_id: entry.id, expected_version: entry.version, entry: { ...entry.data, favorite: !entry.data.favorite } }))} style={{ padding: 12 }}><SavedIcon color={entry.data.favorite ? "#C34768" : palette.mutedText} /></Pressable><Button label={mt("Исправить")} onPress={() => c.setEditor({ page: "meal", entry })} /></View></View>)}
            {mealMode === "favorites" && moreFavorites ? <Copy muted>{mt("Показаны последние 200 избранных записей.")}</Copy> : null}
            {entries.length >= 200 ? <Copy muted>{mt("Показаны последние 200 записей. Сузьте период истории.")}</Copy> : null}
        </> : null}
        {page === "workouts" ? <MentorWorkouts controller={c} entries={entries} onChanged={load} /> : null}
        {page === "course" ? <MentorCourse controller={c} /> : null}
        {page === "progress" ? <MentorProgress controller={c} entries={periodEntries} weeklyEntries={weeklyEntries} summary={summary} days={days} setDays={setDays} progressTab={progressTab} setProgressTab={setProgressTab} onReport={report}
            measurementsContent={<><Button label={mt("Добавить замеры")} primary onPress={() => setMeasurementOpen(true)} />{measurementOpen ? <MeasurementEditor controller={c} save={save} onClose={() => setMeasurementOpen(false)} /> : null}{periodEntries.filter(entry => entry.kind === "measurement").map(entry => <View key={entry.id} style={styles.section}><Copy muted>{formatCompanionDate(entry.occurred_at, c.clock)}</Copy>{Object.entries(entry.data.measurement ?? {}).filter(([, value]) => value != null).map(([key, value]) => <Copy key={key}>{measurementLabels[key as keyof Measurement]}: {value}</Copy>)}</View>)}{!periodEntries.some(entry => entry.kind === "measurement") ? <Copy muted>{mt("Замеров пока нет.")}</Copy> : null}</>}
            photosContent={<><Button label={mt("Добавить фото прогресса")} icon={<CameraIcon width={22} height={22} color={palette.text} />} onPress={() => compose("photo", mt("Фото прогресса. Не оценивай состав тела и здоровье по фотографии."))} /><MentorPhotos controller={c} days={days} messages={photoMessages} renderAttachments={renderPhotoAttachments} /></>}
        /> : null}
        {page === "more" ? <><Copy heading>{mt("Мой наставник")}</Copy><Copy muted>{mt("Ваши цели, история и помощь рядом.")}</Copy><Button label={mt("Спросить наставника")} icon={<MentorIcon name="chat" color="#FFFFFF" />} primary onPress={() => go("ask")} /><View style={styles.row}><ProfileIcon color={colors.green} /><Copy>{c.state?.profile?.data.goal ? goalLabels[c.state.profile.data.goal] : mt("Цель не указана")}{c.state?.profile?.data.custom_goal ? `: ${c.state.profile.data.custom_goal}` : ""}</Copy></View><Copy>{mt("Последний вес: ")}{latest ? mt("{0} кг · {1}", [latest.data.weight_kg, formatCompanionDate(latest.occurred_at, c.clock)]) : mt("не записан")}</Copy><Button label={mt("Профиль и цели")} onPress={() => c.setEditor({ page: "profile" })} /><Button label={mt("Записать вес")} onPress={() => c.setEditor({ page: "weight" })} /><Button label={mt("Прогресс и замеры")} onPress={() => go("progress")} /><Button label={mt("Настройки и напоминания")} onPress={() => c.setEditor({ page: "settings" })} /><Button label={mt("Дневник")} onPress={() => c.setEditor({ page: "journal" })} /><Button label={mt("Написать в поддержку")} onPress={() => router.push({ pathname: "/chat", params: { mode: "support" } })} /></> : null}
        {page === "ask" ? <><Copy heading>{mt("Спросить наставника")}</Copy><Copy muted>{mt("Выберите тему или напишите свой вопрос.")}</Copy>{[
            [mt("🍲 Что поесть?"), mt("Что мне поесть? Учти сохранённые предпочтения, любимые блюда и остаток КБЖУ за сегодня.")],
            [mt("📊 Проанализировать мой день"), mt("Проанализируй мой день по сохранённым записям питания, тренировок и самочувствия.")],
            [mt("🏋️ Скорректировать тренировку"), mt("Помоги скорректировать тренировку с учётом моего плана и записанных результатов.")],
            [mt("⚖️ Почему вес стоит?"), mt("Помоги разобраться в динамике моего веса, учитывая сохранённые измерения и питание.")],
        ].map(([label, prompt]) => <Button key={label} label={label} onPress={() => ask(prompt)} />)}<Button label={mt("🧬 Вопрос по моему курсу")} onPress={() => router.push({ pathname: "/chat", params: { mode: "support" } })} /><Button label={mt("Задать свой вопрос")} icon={<MentorIcon name="chat" color="#FFFFFF" />} primary onPress={() => compose("text", "")} /></> : null}
        {page === "adjust" ? <><Copy heading>{mt("Что скорректировать?")}</Copy><Copy muted>{mt("Выберите, что сейчас не подходит.")}</Copy><Button label={mt("🍽 Не подходит питание")} onPress={() => ask(mt("Хочу скорректировать питание. Используй сохранённую цель, последний вес, предпочтения и подтверждённые записи. Уточни, что именно изменить, и запроси подтверждение."))} /><Button label={mt("🔥 Слишком мало калорий")} onPress={() => ask(mt("Мне не хватает калорий. Проанализируй сохранённую цель, питание и самочувствие, помоги скорректировать план с подтверждением."))} /><Button label={mt("🏋️ Не подходит тренировка")} onPress={() => go("workouts")} /><Button label={mt("📅 Неудобное расписание")} onPress={() => c.setEditor({ page: "settings" })} /><Button label={mt("🧬 Вопрос по курсу")} onPress={() => router.push({ pathname: "/chat", params: { mode: "support" } })} /><Button label={mt("😓 Сложно соблюдать план")} onPress={() => ask(mt("Мне сложно соблюдать план. Помоги выбрать посильный следующий шаг с учётом моих записей."))} /><Button label={mt("Другая причина")} onPress={() => compose("text", mt("Хочу скорректировать план: "))} /><Button label={mt("Цель и профиль")} onPress={() => c.setEditor({ page: "profile" })} /></> : null}
    </View>
}

function NutritionOverview({ nutrition }: { nutrition: MentorDashboard["today"]["nutrition"] }) {
    useLanguage()
    const colors = useMentorPalette()
    const fraction = (value: unknown, target: unknown) => {
        const amount = numeric(value), total = numeric(target)
        return amount != null && total != null && total > 0 ? Math.max(0, Math.min(1, amount / total)) : 0
    }
    return <View style={[styles.notice, { backgroundColor: colors.mint }]}>
        <Copy muted>{mt("Итоги за сегодня")}</Copy>
        <Text style={{ color: colors.green, fontSize: 30, fontWeight: "600" }}>{Number(nutrition.consumed.kcal).toLocaleString(mentorLocale())} <Text style={{ fontSize: 15, fontWeight: "400", color: colors.muted }}>{nutrition.target ? mt("из {0} ", [Number(nutrition.target.kcal).toLocaleString(mentorLocale())]) : ""}{mt("ккал")}</Text></Text>
        {nutrition.target ? <View style={{ height: 7, backgroundColor: colors.surface, borderRadius: 5, overflow: "hidden" }}><View style={{ height: 7, borderRadius: 5, width: `${fraction(nutrition.consumed.kcal, nutrition.target.kcal) * 100}%`, backgroundColor: colors.greenBright }} /></View> : null}
        <View style={styles.row}>{(["protein", "fat", "carbs"] as const).map((key, index) => <View key={key} style={{ flex: 1, gap: 4, paddingTop: 8 }}><Copy muted style={{ fontSize: 12 }}>{[mt("Белки"), mt("Жиры"), mt("Углеводы")][index]}</Copy><Copy style={{ fontSize: 16, fontWeight: "600", color: colors.green }}>{nutrition.consumed[key]} {mt(" г")}</Copy>{nutrition.target ? <Copy muted style={{ fontSize: 12 }}>{mt("из ")}{nutrition.target[key]} {mt(" г")}</Copy> : null}</View>)}</View>
        {nutrition.remaining ? <Copy style={{ color: colors.green }}>{mt("Осталось ")}{nutrition.remaining.kcal} {mt(" ккал · ")}{nutrition.remaining.protein} {mt(" г белка")}</Copy> : null}
    </View>
}

function MealCopy({ entry }: { entry: CompanionEntry }) {
    useLanguage()
    return <><Copy heading>{entry.data.name || mt("Приём пищи")}</Copy>{entry.data.nutrition ? <Copy>{entry.data.nutrition.kcal} {mt(" ккал · Б ")}{entry.data.nutrition.protein} {mt(" · Ж ")}{entry.data.nutrition.fat} {mt(" · У ")}{entry.data.nutrition.carbs} {mt(" г")}</Copy> : null}{entry.data.estimated ? <Copy muted>{mt("Оценка: ")}{entry.data.assumptions || mt("порция и состав требуют проверки")}</Copy> : null}</>
}
function MeasurementEditor({ controller: c, save, onClose }: { controller: Controller; save: (action: CompanionAction) => Promise<void>; onClose: () => void }) {
    useLanguage()
    const [measurement, setMeasurement] = useState<Measurement>({})
    const original = useRef(new Date().toISOString())
    const [date, setDate] = useState(localDateTime(original.current))
    return <View style={styles.section}><Field label={mt("Дата и время, ГГГГ-ММ-ДД ЧЧ:ММ")} value={date} onChange={setDate} />{(Object.keys(measurementLabels) as (keyof Measurement)[]).map(key => <Field key={key} label={measurementLabels[key]} numeric value={measurement[key]} onChange={text => setMeasurement({ ...measurement, [key]: text.trim() ? text.replace(",", ".") : null })} />)}<Button label={mt("Подтвердить замеры")} primary disabled={c.busy || !Object.values(measurement).some(value => value != null) || Object.values(measurement).some(value => value != null && (numeric(value) == null || Number(value) <= 0))} onPress={() => void c.attempt(async () => { const entry: EntryData = { kind: "measurement", occurred_at: localEntryTimestamp(date, original.current), measurement }; await save({ kind: "entry", entry }); onClose() })} /><Button label={mt("Отмена")} onPress={onClose} /></View>
}

function MentorCourse({ controller: c }: { controller: Controller }) {
    const { language } = useLanguage()
    LocaleConfig.defaultLocale = `mentor-${language}`
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
    return <><Copy heading>{mt("Мой курс")}</Copy><Copy muted>{mt("Только ваша готовая схема. Изменения назначений обсуждаются со специалистом.")}</Copy>
        {plan ? <><Copy heading>{plan.data.name}</Copy><Copy>{plan.status === "active" ? mt("Активен") : plan.status === "paused" ? mt("На паузе") : mt("Завершён")}</Copy>{plan.data.items.map((item, index) => <View key={index} style={styles.section}><Copy>{item.name}</Copy>{item.stages.map((stage, i) => <Copy key={i}>{stage.start_date} – {stage.end_date} · {stage.amount} {mentorUnitLabel(stage.unit)} · {stage.times.join(", ")}</Copy>)}</View>)}</> : <Copy muted>{mt("Готовая схема пока не сохранена.")}</Copy>}
        <Button label={plan ? mt("Обновить мою схему") : mt("Записать готовую схему")} onPress={() => c.setEditor({ page: "plan" })} />
        {plan?.status === "active" ? <Button label={mt("Приостановить напоминания курса")} disabled={c.busy} onPress={() => void c.attempt(async () => { await c.perform({ kind: "plan_status", expected_version: c.state?.profile?.version, status: "paused" }); await load() })} /> : null}
        {plan && plan.status !== "completed" ? <Button label={mt("Завершить учёт курса")} disabled={c.busy} onPress={() => Alert.alert(mt("Завершить учёт курса?"), mt("Будущие напоминания будут отменены. История сохранится."), [{ text: mt("Отмена"), style: "cancel" }, { text: mt("Завершить"), onPress: () => void c.attempt(async () => { await c.perform({ kind: "plan_status", expected_version: c.state?.profile?.version, status: "completed" }); await load() }) }])} /> : null}
        <Calendar key={language} theme={{ backgroundColor: colors.soft, calendarBackground: colors.soft, dayTextColor: colors.text, monthTextColor: colors.green, arrowColor: colors.green, todayTextColor: colors.green, textDisabledColor: colors.muted, textSectionTitleColor: colors.muted, selectedDayBackgroundColor: colors.greenBright, selectedDayTextColor: "#FFFFFF", dotColor: colors.greenBright }} style={{ borderRadius: 18, padding: 8 }} current={`${month}-01`} onDayPress={day => setDate(day.dateString)} onMonthChange={value => setMonth(value.dateString.slice(0, 7))} markedDates={{ ...markedDates, [date]: { ...markedDates[date], selected: true, selectedColor: "#176B4A" } }} firstDay={1} />
        {loading ? <ActivityIndicator /> : null}<Copy heading>{date}</Copy>
        {events.filter(event => localDay(event) === date).map(event => <View key={event.id} style={styles.section}><Copy>{event.data.name} · {event.data.amount} {mentorUnitLabel(event.data.unit)}</Copy><Copy muted>{formatCompanionDate(event.scheduled_at, c.clock)} · {event.status === "done" ? mt("Выполнено") : event.status === "skipped" ? mt("Пропущено") : mt("Без отметки")}</Copy><View style={styles.row}>{(["done", "skipped", "pending"] as const).filter(status => status !== event.status).map(status => <Button key={status} label={status === "done" ? mt("Отметить") : status === "skipped" ? mt("Пропущено") : mt("Снять отметку")} disabled={c.busy || status === "done" && Date.parse(event.scheduled_at) > Date.now()} onPress={() => void c.attempt(async () => { const identity = `${event.id}:${event.version}:${status}`; const key = keys.current.get(identity) ?? requestKey(); keys.current.set(identity, key); await c.perform({ kind: "event", resource_id: event.id, expected_version: event.version, request_key: key, status }); keys.current.delete(identity); await load() })} />)}</View></View>)}
        {!loading && !events.some(event => localDay(event) === date) ? <Copy muted>{mt("На этот день нет событий.")}</Copy> : null}
        {events.length >= 200 ? <Copy muted>{mt("Показаны первые 200 событий. Полную историю можно открыть отдельно.")}</Copy> : null}
        <Button label={mt("Изменить время напоминаний")} icon={<MentorIcon name="clock" color={colors.green} />} onPress={() => c.setEditor({ page: "settings" })} /><Button label={mt("Запас по моей схеме")} onPress={() => c.setEditor({ page: "supply" })} /><Button label={mt("Самочувствие")} onPress={() => c.setEditor({ page: "wellbeing" })} /><Button label={mt("История событий")} onPress={() => c.setEditor({ page: "events" })} /><Copy muted>{mt("Контакт врача пока не настроен.")}</Copy><Button label={mt("Написать в поддержку")} onPress={() => router.push({ pathname: "/chat", params: { mode: "support" } })} />
    </>
}
