import { mentorText as mt, mentorLocale, mentorDateLabel } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { QuietLoading } from "@/components/ui/quiet-loading"
import { useState } from "react"
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native"
import Svg, { Circle, G, Line, Polyline, Text as SvgText } from "react-native-svg"
import type { CompanionEntry, Summary } from "@/services/api/companion"
import type { useCompanion } from "@/screens/chat/companion"
import { calendarDate, formatCompanionDate } from "@/screens/chat/companion-timezones"
import { numeric, recordedMean, weightPoints, workoutTotals } from "@/screens/chat/mentor-data"
import { MentorButton as Button, MentorTabs as Tabs, MentorText as Copy, useMentorPalette } from "@/screens/chat/mentor-ui"

export type MentorProgressTab = "weight" | "nutrition" | "workouts" | "course" | "measurements" | "photos"
type Controller = ReturnType<typeof useCompanion>
type Props = {
    controller: Controller
    entries: CompanionEntry[]
    weeklyEntries: CompanionEntry[]
    summary: Summary | null
    days: 7 | 30
    setDays: (days: 7 | 30) => void
    progressTab: MentorProgressTab
    setProgressTab: (tab: MentorProgressTab) => void
    onReport: (days: 7 | 30) => void
    measurementsContent: React.ReactNode
    photosContent: React.ReactNode
}

const primaryTabs = { get weight() { return mt("Вес") }, get nutrition() { return mt("Питание") }, get workouts() { return mt("Тренировки") }, get course() { return mt("Курс") } } as const
const number = (value: unknown, digits = 1) => {
    const parsed = numeric(value)
    return parsed == null ? "—" : parsed.toLocaleString(mentorLocale(), { maximumFractionDigits: digits })
}
const signedWeight = (value: number) => mt("{0}{1} кг", [value > 0 ? "+" : value < 0 ? "−" : "", number(Math.abs(value))])
function periodLabel(days: 7 | 30) {
    const start = new Date(`${calendarDate(1 - days)}T12:00:00`)
    const end = new Date(`${calendarDate()}T12:00:00`)
    if (mentorLocale() === "kk-KZ") return `${mentorDateLabel(start, { day: "numeric", month: "short" })} – ${mentorDateLabel(end, { day: "numeric", month: "short" })}`
    const formatter = new Intl.DateTimeFormat(mentorLocale(), { day: "numeric", month: "short" })
    return typeof formatter.formatRange === "function"
        ? formatter.formatRange(start, end)
        : `${formatter.format(start)} – ${formatter.format(end)}`
}

export function MentorProgress({ controller: c, entries, weeklyEntries, summary, days, setDays, progressTab, setProgressTab, onReport, measurementsContent, photosContent }: Props) {
    useLanguage()
    const colors = useMentorPalette()
    const [detailsOpen, setDetailsOpen] = useState(false)
    const [selectedWeight, setSelectedWeight] = useState<number | null>(null)
    const [width, setWidth] = useState(340)
    const points = weightPoints(entries)
    const average = recordedMean(weeklyEntries, "weight", "weight_kg")
    const latest = numeric(c.state?.mentor?.latest_weight?.data.weight_kg)
    const target = numeric(c.state?.profile?.data.target_weight_kg)
    const change = numeric(summary?.weight_change_kg)
    const secondaryTab = progressTab === "measurements" || progressTab === "photos"
    const expanded = detailsOpen || secondaryTab
    const selected = points.find(point => point.id === selectedWeight) ?? points[points.length - 1]
    const workouts = entries.filter(entry => entry.kind === "workout" && entry.data.workout)
    const eventsTotal = summary ? summary.events.done + summary.events.skipped + summary.events.pending : 0
    const insight = !summary
        ? mt("Загружаем ваши измерения и сводку…")
        : change == null
            ? mt("Добавьте хотя бы два измерения веса за выбранный период, чтобы увидеть изменение.")
            : change === 0
                ? mt("Первый и последний записанный вес совпадают. Продолжайте отмечать измерения, чтобы видеть динамику.")
                : mt("За {0} дней вес {1} на {2} кг. Продолжайте отмечать измерения.", [days, change < 0 ? mt("снизился") : mt("увеличился"), number(Math.abs(change))])
    const addData = () => {
        if (progressTab === "nutrition") c.setEditor({ page: "meal" })
        else if (progressTab === "workouts" || progressTab === "course") c.setMentorPage(progressTab)
        else c.setEditor({ page: "weight" })
    }

    return <View testID="mentor-progress" onLayout={event => setWidth(event.nativeEvent.layout.width)} style={styles.screen}>
        <View style={styles.headingRow}>
            <Text style={[styles.heading, { color: colors.text, fontSize: width < 400 ? 20 : 27 }]}>{mt("Прогресс за {0} дней", [days])}</Text>
            <Text style={[styles.period, { color: colors.muted, fontSize: width < 400 ? 12 : 14 }]}>{periodLabel(days)}</Text>
        </View>
        <View accessibilityRole="tablist" accessibilityLabel={mt("Раздел прогресса")} style={styles.mainTabs}>
            {(Object.keys(primaryTabs) as (keyof typeof primaryTabs)[]).map(tab => <Pressable key={tab} accessibilityRole="tab" accessibilityLabel={primaryTabs[tab]} accessibilityState={{ selected: progressTab === tab }} onPress={() => setProgressTab(tab)} style={[styles.mainTab, { flex: width < 290 && tab === "workouts" ? 1.28 : 1, backgroundColor: progressTab === tab ? "#1C694B" : colors.soft }]}>
                <Text style={{ color: progressTab === tab ? "#FFFFFF" : colors.muted, fontSize: width < 290 ? 10 : width < 350 ? 12 : 15, lineHeight: width < 290 ? 13 : 19, flexShrink: 1, textAlign: "center" }}>{primaryTabs[tab]}</Text>
            </Pressable>)}
        </View>

        {!summary ? <QuietLoading loading /> : <>
        {progressTab === "weight" ? <>
            <Metric label={mt("Изменение веса")} value={change == null ? "—" : signedWeight(change)} />
            {points.length ? <WeightChart clock={c.clock} entries={entries} selectedId={selected?.id} onSelect={setSelectedWeight} /> : <View style={[styles.emptyChart, { borderColor: colors.border, backgroundColor: colors.soft }]}>
                {!summary ? <QuietLoading loading /> : null}
                <Text style={[styles.emptyTitle, { color: colors.green }]}>{summary ? mt("Здесь будет ваш график") : mt("Загружаем измерения")}</Text>
                <Text style={[styles.emptyCopy, { color: colors.muted }]}>{summary ? mt("В этом периоде пока нет записей веса. Добавьте первое измерение.") : mt("График появится после загрузки данных.")}</Text>
            </View>}
            <View style={[styles.insight, { backgroundColor: colors.mint }]}><Text style={[styles.insightCopy, { color: colors.text }]}>{insight}</Text></View>
        </> : null}

        {progressTab === "nutrition" ? <>{summary ? <>
            <Metric label={mt("Калории за {0} дней", [days])} value={mt("{0} ккал", [number(summary.nutrition.kcal, 0)])} />
            <Text style={[styles.subheading, { color: colors.text }]}>{mt("{0} приёмов пищи за {1} дней с записями", [summary.meals_logged, summary.days_with_meals])}</Text>
            <View style={styles.statRow}>{(["protein", "fat", "carbs"] as const).map((key, index) => <Stat key={key} label={[mt("Белки"), mt("Жиры"), mt("Углеводы")][index]} value={mt("{0} г", [number(summary.nutrition[key])])} />)}</View>
            <View style={[styles.insight, { backgroundColor: colors.mint }]}><Copy>{summary.days_with_meals ? mt("В среднем {0} ккал за день с записями.", [number(Number(summary.nutrition.kcal) / summary.days_with_meals, 0)]) : mt("Добавьте первый приём пищи, чтобы видеть итоги питания.")}</Copy><Copy muted>{mt(summary.coverage_note)}</Copy></View>
        </> : <QuietLoading loading />}</> : null}

        {progressTab === "workouts" ? <>
            <Metric label={mt("Завершено тренировок")} value={summary?.workouts ? String(summary.workouts.completed) : "—"} />
            {summary?.workouts ? <><View style={styles.statRow}><Stat label={mt("Подходы")} value={number(summary.workouts.completed_sets, 0)} /><Stat label={mt("Повторения")} value={number(summary.workouts.reps, 0)} /><Stat label={mt("Минуты")} value={String(Math.round(summary.workouts.duration_seconds / 60))} /></View><View style={[styles.insight, { backgroundColor: colors.mint }]}><Copy>{mt("Общий объём: ")}{number(summary.workouts.volume_kg)} {mt(" кг")}</Copy><Copy muted>{mt("В процессе: ")}{summary.workouts.in_progress}</Copy></View></> : !summary ? <QuietLoading loading /> : null}
            {workouts.length ? workouts.map(entry => { const workout = entry.data.workout!; const totals = workoutTotals(workout); return <View key={entry.id} style={[styles.record, { backgroundColor: colors.soft }]}><Copy heading>{workout.name}</Copy><Copy muted>{workout.status === "completed" ? mt("Завершена") : mt("В процессе")} · {formatCompanionDate(entry.occurred_at, c.clock)}</Copy><Copy>{totals.sets} {mt(" подходов · ")}{number(totals.volume)} {mt(" кг · ")}{Math.round(workout.duration_seconds / 60)} {mt(" мин")}</Copy></View> }) : summary ? <Copy muted>{mt("Нет записей тренировок в загруженной истории.")}</Copy> : null}
        </> : null}

        {progressTab === "course" ? <>{summary ? <>
            <Metric label={mt("Выполнение курса")} value={eventsTotal ? `${Math.round(summary.events.done / eventsTotal * 100)}%` : "—"} />
            <View style={styles.statRow}><Stat label={mt("Выполнено")} value={String(summary.events.done)} /><Stat label={mt("Пропущено")} value={String(summary.events.skipped)} /><Stat label={mt("Без отметки")} value={String(summary.events.pending)} /></View>
            {eventsTotal ? <View accessibilityLabel={mt("Выполнено {0} из {1} событий", [summary.events.done, eventsTotal])} style={[styles.completionTrack, { backgroundColor: colors.soft }]}><View style={{ height: "100%", width: `${summary.events.done / eventsTotal * 100}%`, backgroundColor: colors.greenBright, borderRadius: 8 }} /></View> : null}
            <View style={[styles.insight, { backgroundColor: colors.mint }]}><Copy>{eventsTotal ? mt("Все отметки по вашей сохранённой схеме собраны здесь.") : mt("В выбранном периоде нет событий курса.")}</Copy><Copy muted>{mt(summary.coverage_note)}</Copy></View>
        </> : <QuietLoading loading />}</> : null}

        {!secondaryTab ? <View style={styles.actionRow}>
            <Pressable accessibilityRole="button" accessibilityLabel={mt("Добавить данные")} onPress={addData} style={({ pressed }) => [styles.mainAction, { backgroundColor: "#1C694B", opacity: pressed ? 0.76 : 1 }]}><Text style={[styles.mainActionText, { color: "#FFFFFF", fontSize: width < 290 ? 12 : width < 400 ? 16 : 17 }]}>{mt("Добавить данные")}</Text></Pressable>
            <Pressable accessibilityRole="button" accessibilityLabel={mt("Отчёт за 30 дней")} accessibilityState={{ disabled: c.busy }} disabled={c.busy} onPress={() => onReport(30)} style={({ pressed }) => [styles.mainAction, { backgroundColor: colors.soft, opacity: c.busy ? 0.45 : pressed ? 0.76 : 1 }]}><Text style={[styles.mainActionText, { color: colors.text, fontSize: width < 290 ? 12 : width < 400 ? 16 : 17 }]}>{mt("Отчёт за 30 дней")}</Text></Pressable>
        </View> : null}

        <Pressable accessibilityRole="button" accessibilityLabel={mt("Детали прогресса: замеры, фото и период")} accessibilityState={{ expanded }} onPress={() => { setDetailsOpen(!expanded); if (secondaryTab) setProgressTab("weight") }} style={[styles.detailsToggle, { borderColor: colors.border }]}>
            <Text style={{ color: colors.muted, fontSize: 13 }}>{mt("Замеры, фото и подробности")}</Text><Text style={{ color: colors.green, fontSize: 18 }}>{expanded ? "⌃" : "⌄"}</Text>
        </Pressable>
        {expanded ? <View style={styles.details}>
            <Tabs items={{ "7": mt("7 дней"), "30": mt("30 дней") }} value={String(days) as "7" | "30"} onChange={value => setDays(Number(value) as 7 | 30)} />
            <Tabs items={{ measurements: mt("Замеры"), photos: mt("Фото") }} value={secondaryTab ? progressTab : null} onChange={setProgressTab} />
            {progressTab === "measurements" ? measurementsContent : progressTab === "photos" ? photosContent : <>
                <View style={styles.statRow}><Stat label={mt("Текущий вес")} value={latest == null ? mt("Нет записи") : mt("{0} кг", [number(latest)])} /><Stat label={mt("Средний за 7 дней")} value={average.value == null ? mt("Нет измерений") : mt("{0} кг", [number(average.value, 2)])} /></View>
                <Copy muted>{mt("Средний вес рассчитан по {0} измерениям за 7 дней.", [average.count])}</Copy>
                {weeklyEntries.length >= 200 ? <Copy muted>{mt("Среднее рассчитано по последним 200 измерениям.")}</Copy> : null}
                {target != null && latest != null ? <Copy>{mt("Цель: ")}{number(target)} {mt(" кг · до цели ")}{number(Math.abs(target - latest))} {mt(" кг")}</Copy> : null}
                <Copy muted>{mt("Энергия за ")}{days} {mt(" дней: ")}{summary?.wellbeing?.average_energy == null ? mt("нет данных") : mt("{0}/5 · {1} измерений", [number(summary.wellbeing.average_energy), summary.wellbeing.energy_measurements ?? "—"])}</Copy>
                {progressTab === "weight" && selected ? <>
                    <Copy>{formatCompanionDate(selected.date, c.clock)} · {number(selected.value)} {mt(" кг")}</Copy>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false}><View style={styles.pointList}>{points.map(point => <Button key={point.id} label={mt("{0} · {1} кг", [mentorDateLabel(new Date(point.date), { day: "numeric", month: "short" }), number(point.value)])} primary={point.id === selected.id} onPress={() => setSelectedWeight(point.id)} />)}</View></ScrollView>
                </> : null}
                {summary ? <Copy muted>{mt(summary.coverage_note)} {mt(" Вес не показывает состав тела.")}</Copy> : null}
            </>}
            <Button label={mt("Отчёт за {0} дней в диалоге", [days])} onPress={() => onReport(days)} disabled={c.busy} />
        </View> : null}
        </>}
    </View>
}

function Metric({ label, value }: { label: string; value: string }) {
    useLanguage()
    const colors = useMentorPalette()
    return <View style={styles.metric}><Text style={[styles.metricLabel, { color: colors.muted }]}>{label}</Text><Text style={[styles.metricValue, { color: colors.green }]}>{value}</Text></View>
}

function Stat({ label, value }: { label: string; value: string }) {
    useLanguage()
    const colors = useMentorPalette()
    return <View style={[styles.stat, { backgroundColor: colors.soft }]}><Text style={[styles.statLabel, { color: colors.muted }]}>{label}</Text><Text style={[styles.statValue, { color: colors.green }]}>{value}</Text></View>
}

function WeightChart({ clock, entries, selectedId, onSelect }: { clock: string; entries: CompanionEntry[]; selectedId?: number; onSelect: (id: number) => void }) {
    useLanguage()
    const colors = useMentorPalette()
    const [width, setWidth] = useState(340)
    const source = weightPoints(entries)
    const height = Math.min(360, Math.max(230, width * 0.65))
    const left = width < 350 ? 53 : 64, right = width - 19, top = 19, bottom = height - 61
    const values = source.map(point => point.value)
    const smallest = Math.min(...values), largest = Math.max(...values)
    const padding = Math.max((largest - smallest) * 0.15, 0.15)
    const low = Math.floor((smallest - padding) * 10) / 10, high = Math.ceil((largest + padding) * 10) / 10
    const start = source[0].time, end = source[source.length - 1].time
    const points = source.map(point => ({ ...point, x: start === end ? (left + right) / 2 : left + (point.time - start) / (end - start) * (right - left), y: top + (high - point.value) / (high - low) * (bottom - top) }))
    const selected = points.find(point => point.id === selectedId) ?? points[points.length - 1]
    const tickCount = Math.min(points.length, 4)
    const ticks = [...new Set(Array.from({ length: tickCount }, (_, index) => Math.round(index * (points.length - 1) / Math.max(tickCount - 1, 1))))].map(index => points[index])
    const sameMonth = new Date(source[0].date).getMonth() === new Date(source[source.length - 1].date).getMonth()
    const monthLabel = sameMonth ? mentorDateLabel(new Date(source[0].date), { month: "long" }) : mt("Дата измерения")

    return <View testID="mentor-weight-chart" onLayout={event => setWidth(Math.max(200, event.nativeEvent.layout.width))} style={{ width: "100%", height }}>
        <Svg accessible={false} width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
            {[0, 1, 2, 3].map(index => { const y = top + index / 3 * (bottom - top); return <G key={index}><Line x1={left} x2={right} y1={y} y2={y} stroke={colors.border} strokeWidth={1} /><SvgText x={left - 9} y={y + 4} textAnchor="end" fill={colors.muted} fontFamily="Arial" fontSize={12}>{number(high - index / 3 * (high - low))}</SvgText></G> })}
            <Line x1={left} x2={left} y1={top} y2={bottom} stroke={colors.border} strokeWidth={1} />
            <Line x1={right} x2={right} y1={top} y2={bottom} stroke={colors.border} strokeWidth={1} />
            <SvgText x={14} y={(top + bottom) / 2} rotation={-90} origin={`14, ${(top + bottom) / 2}`} textAnchor="middle" fill={colors.text} fontFamily="Arial" fontSize={12}>{mt("Вес, кг")}</SvgText>
            <Polyline points={points.map(point => `${point.x},${point.y}`).join(" ")} fill="none" stroke={colors.greenBright} strokeWidth={3} strokeLinejoin="round" strokeLinecap="round" />
            {points.map(point => <Circle key={point.id} cx={point.x} cy={point.y} r={point.id === selected?.id ? 5.5 : 5} fill={colors.surface} stroke={colors.greenBright} strokeWidth={2.5} />)}
            {ticks.map(point => <SvgText key={point.id} x={point.x} y={bottom + 23} textAnchor="middle" fill={colors.muted} fontFamily="Arial" fontSize={12}>{mentorDateLabel(new Date(point.date), sameMonth ? { day: "numeric" } : { day: "numeric", month: "short" })}</SvgText>)}
            <SvgText x={(left + right) / 2} y={height - 9} textAnchor="middle" fill={colors.text} fontFamily="Arial" fontSize={14}>{monthLabel.charAt(0).toUpperCase() + monthLabel.slice(1)}</SvgText>
            {selected ? <SvgText x={selected.x > width / 2 ? selected.x - 9 : selected.x + 9} y={Math.max(top + 12, selected.y - 12)} textAnchor={selected.x > width / 2 ? "end" : "start"} fill={colors.muted} fontFamily="Arial" fontSize={12}>{number(selected.value)} {mt(" кг")}</SvgText> : null}
        </Svg>
        {points.map(point => <Pressable key={point.id} accessibilityRole="button" accessibilityLabel={mt("{0} · {1} кг", [formatCompanionDate(point.date, clock), number(point.value)])} accessibilityState={{ selected: point.id === selectedId }} onPress={() => onSelect(point.id)} style={{ position: "absolute", left: Math.min(width - 44, Math.max(0, point.x - 22)), top: point.y - 22, width: 44, height: 44, borderRadius: 22 }} />)}
    </View>
}

const styles = StyleSheet.create({
    screen: { width: "100%", gap: 14 },
    headingRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", columnGap: 10, rowGap: 3 },
    heading: { fontWeight: "500", lineHeight: 36, flexShrink: 1 },
    period: { fontSize: 14, lineHeight: 24 },
    mainTabs: { flexDirection: "row", gap: 5 },
    mainTab: { minWidth: 0, flex: 1, minHeight: 43, borderRadius: 13, paddingHorizontal: 3, paddingVertical: 10, alignItems: "center", justifyContent: "center" },
    metric: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 8, paddingTop: 1 },
    metricLabel: { fontSize: 16, lineHeight: 24, flexShrink: 1 },
    metricValue: { fontSize: 29, lineHeight: 38, fontWeight: "500" },
    insight: { borderRadius: 17, padding: 15, gap: 8 },
    insightCopy: { fontSize: 16, lineHeight: 23 },
    emptyChart: { minHeight: 230, padding: 25, borderRadius: 18, borderWidth: 1, alignItems: "center", justifyContent: "center", gap: 12 },
    emptyTitle: { fontSize: 19, fontWeight: "600", textAlign: "center" },
    emptyCopy: { fontSize: 15, lineHeight: 22, textAlign: "center" },
    actionRow: { flexDirection: "row", gap: 9, alignItems: "stretch" },
    mainAction: { flex: 1, minHeight: 49, borderRadius: 15, paddingHorizontal: 8, paddingVertical: 12, justifyContent: "center", alignItems: "center" },
    mainActionText: { lineHeight: 23, textAlign: "center", fontWeight: "500", flexShrink: 1 },
    detailsToggle: { minHeight: 40, paddingTop: 8, borderTopWidth: StyleSheet.hairlineWidth, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
    details: { gap: 13 },
    statRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    stat: { borderRadius: 15, padding: 12, flexGrow: 1, flexBasis: 90, gap: 7 },
    statLabel: { fontSize: 12, lineHeight: 18 },
    statValue: { fontSize: 20, lineHeight: 26, fontWeight: "600" },
    subheading: { fontSize: 17, lineHeight: 25 },
    record: { padding: 15, gap: 7, borderRadius: 15 },
    completionTrack: { height: 12, overflow: "hidden", borderRadius: 8 },
    pointList: { flexDirection: "row", gap: 7 },
})
