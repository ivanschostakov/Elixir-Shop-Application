import { useCallback, useEffect, useRef, useState } from "react"
import { ActivityIndicator, Pressable, ScrollView, Text, View, useWindowDimensions } from "react-native"
import type { CalendarProps } from "react-native-calendars"
import { MentorCalendarHeader } from "@/screens/chat/mentor-calendar-header"
import { AppCalendar } from "@/components/platform/app-calendar"
import { mentorNumber, mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { MentorHomeHeader } from "@/screens/chat/mentor-home"
import { calendarDate } from "@/screens/chat/companion-timezones"
import type { useCompanion } from "@/screens/chat/companion"
import { MentorIcon, useMentorPalette } from "@/screens/chat/mentor-ui"
import { getCompanionEntries, type CompanionEntry } from "@/services/api/companion"
import { getErrorMessage } from "@/utils/errors"
import { loadWellbeingMonth, wellbeingDateLabel, wellbeingDays, wellbeingDraft, wellbeingSummary } from "@/screens/chat/mentor-wellbeing-data"
import { WellbeingIcon, type WellbeingIconName } from "@/screens/chat/mentor-wellbeing-icons"
import { wellbeingStyles as styles } from "@/screens/chat/mentor-wellbeing.styles"

type Controller = ReturnType<typeof useCompanion>
const overview: { index: number; icon: WellbeingIconName; level: number }[] = [
    { index: 0, icon: "face", level: 4 }, { index: 1, icon: "energy", level: 2 },
    { index: 4, icon: "moon", level: 2 }, { index: 6, icon: "apple", level: 1 },
]

export function MentorWellbeingScreen({ controller: c, active, onClose, onSettings }: { controller: Controller; active: boolean; onClose: () => void; onSettings: () => void }) {
    const { language } = useLanguage()
    const { isDark } = useTheme()
    const colors = useMentorPalette()
    const today = calendarDate()
    const window = useWindowDimensions()
    const [height, setHeight] = useState(Math.max(360, window.height - 160))
    const dense = height < 560
    const compact = height < 680
    const gap = dense ? 6 : compact ? 8 : 12
    const weekMargin = dense ? 0 : compact ? 2 : 4
    const introHeight = dense ? 50 : compact ? 58 : 64
    const metricHeight = dense ? 48 : compact ? 60 : 72
    const dateHeight = dense ? 28 : 36
    const cardHeight = dateHeight + gap + metricHeight * 2
    const footerHeight = 76
    const weightCardHeight = compact ? 62 : 74
    const calendarRoom = height - 56 - introHeight - cardHeight - footerHeight - weightCardHeight - gap * 3 - (dense ? 0 : 6)
    const daySize = Math.max(20, Math.min(40, Math.floor((calendarRoom - 80) / 6 - weekMargin * 2)))
    const calendarHeight = 80 + 6 * (daySize + weekMargin * 2)
    const Body = calendarHeight > calendarRoom ? ScrollView : View
    const bodySpacing = { paddingTop: dense ? 0 : 6, gap }
    const [month, setMonth] = useState(today.slice(0, 7))
    const [selected, setSelected] = useState(today)
    const [snapshot, setSnapshot] = useState<{ key: string; entries: CompanionEntry[] } | null>(null)
    const snapshotRef = useRef(snapshot)
    snapshotRef.current = snapshot
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState("")
    const [revision, setRevision] = useState(0)
    const sequence = useRef(0)
    const key = `${month}|${c.clock}`
    const recordsVersion = (c.state?.entries ?? []).filter(entry => entry.kind === "wellbeing").map(entry => `${entry.id}:${entry.version}:${entry.occurred_at}`).sort().join("|")
    useEffect(() => {
        if (!active) return
        const token = ++sequence.current
        let cancelled = false
        // A background refresh keeps the current calendar, button and card geometry.
        if (snapshotRef.current?.key !== key) setLoading(true)
        setError("")
        void loadWellbeingMonth(month, (from, to) => !cancelled && token === sequence.current ? getCompanionEntries(from, to, "wellbeing") : Promise.resolve({ entries: [] }))
            .then(entries => { if (!cancelled && token === sequence.current) setSnapshot({ key, entries }) })
            .catch(failure => { if (!cancelled && token === sequence.current) setError(getErrorMessage(failure)) })
            .finally(() => { if (!cancelled && token === sequence.current) setLoading(false) })
        return () => { cancelled = true }
    }, [active, month, key, revision, c.wellbeingRevision, recordsVersion])
    const entries = snapshot?.key === key ? snapshot.entries : []
    const days = wellbeingDays(entries, c.clock, today)
    const entry = days[selected]
    const ready = !loading && !error && snapshot?.key === key
    const open = useCallback((day: string, original?: CompanionEntry) => {
        if (!ready || c.busy || day > today) return
        setSelected(day)
        c.setEditor({ page: "wellbeing", date: day, ...(original ? { entry: original } : {}) })
    }, [ready, c, today])
    const marks: NonNullable<CalendarProps["markedDates"]> = Object.fromEntries(Object.keys(days).map(day => [day, { marked: true, dotColor: colors.greenBright }]))
    marks[selected] = { ...marks[selected], selected: true, selectedColor: colors.green, selectedTextColor: "#FFFFFF" }
    const summary = wellbeingSummary(wellbeingDraft(entry?.data))
    const statusLabel = loading ? mt("Загружаем записи") : entry ? mt("Заполнено") : error ? mt("Нет данных") : mt("Пока нет записи")
    const weight = c.state?.mentor?.latest_weight?.data.weight_kg
    const buttonLabel = error ? mt("Попробовать ещё раз") : entry ? mt("Изменить запись") : mt("Заполнить анкету")
    return <View testID="mentor-wellbeing" onLayout={event => setHeight(event.nativeEvent.layout.height)} style={[styles.screen, { backgroundColor: colors.surface }]}>
        <MentorHomeHeader title={mt("Самочувствие")} onBack={onClose} onSettings={onSettings} />
        <Body style={[styles.mainBody, Body === View && bodySpacing]} contentContainerStyle={Body === ScrollView ? bodySpacing : undefined}>
            <Pressable accessibilityRole="button" accessibilityLabel={weight == null ? mt("Записать вес") : mt("Записать вес, последнее измерение {0} кг", [mentorNumber(Number(weight))])}
                accessibilityState={{ disabled: c.busy }} disabled={c.busy} onPress={() => c.setEditor({ page: "weight" })}
                style={({ pressed }) => [styles.weightCard, { minHeight: weightCardHeight, backgroundColor: isDark ? "#21392E" : "#EBF4ED", opacity: c.busy ? 0.55 : pressed ? 0.78 : 1 }]}>
                <View style={[styles.weightIcon, { backgroundColor: colors.surface }]}><MentorIcon name="scale" color={colors.green} size={24} /></View>
                <View style={styles.metricCopy}>
                    <Text style={[styles.weightLabel, { color: colors.text }]}>{mt("Вес тела")}</Text>
                    <Text style={[styles.weightValue, { color: colors.green }]}>{weight == null ? mt("Нет измерений") : mt("{0} кг", [mentorNumber(Number(weight))])}</Text>
                </View>
                <View style={[styles.weightAction, { backgroundColor: isDark ? "#2B7552" : "#206647" }]}>
                    <MentorIcon name="plus" size={16} color="#FFF" /><Text style={styles.weightActionText}>{mt("Записать")}</Text>
                </View>
            </Pressable>
            <AppCalendar key={`${language}|${isDark}|${daySize}|${weekMargin}`} current={`${month}-01`} maxDate={today} firstDay={1} hideExtraDays disableMonthChange disableAllTouchEventsForDisabledDays disableArrowRight={month >= today.slice(0, 7)} disabledByDefault={!ready}
                customHeader={MentorCalendarHeader} markedDates={marks} onMonthChange={date => {
                    const next = date.dateString.slice(0, 7)
                    setMonth(next)
                    setSelected(previous => previous.startsWith(next) ? previous : next === today.slice(0, 7) ? today : `${next}-01`)
                }}
                onDayPress={date => open(date.dateString, days[date.dateString])}
                dayComponent={({ date, marking }) => {
                    if (!date || date.dateString.slice(0, 7) !== month) return <View style={{ height: daySize }} />
                    const disabled = !ready || date.dateString > today
                    return <Pressable testID={`wellbeing-day-${date.dateString}`} accessibilityRole="button" accessibilityLabel={wellbeingDateLabel(date.dateString)} accessibilityState={{ selected: !!marking?.selected, disabled }} disabled={disabled} hitSlop={3} onPress={() => open(date.dateString, days[date.dateString])}
                        style={{ height: daySize, width: Math.max(32, daySize), alignItems: "center", justifyContent: "center" }}>
                        <View style={{ width: daySize, height: daySize, borderRadius: daySize / 2, alignItems: "center", justifyContent: "center", backgroundColor: marking?.selected ? colors.green : "transparent" }}><Text style={{ fontSize: dense ? 14 : 17, fontWeight: "500", color: marking?.selected ? "#FFFFFF" : disabled ? colors.muted : colors.text }}>{date.day}</Text></View>
                        {marking?.marked ? <View style={{ position: "absolute", bottom: 1, width: 3, height: 3, borderRadius: 2, backgroundColor: marking.selected ? "#FFFFFF" : colors.greenBright }} /> : null}
                    </Pressable>
                }}
                theme={{ calendarBackground: colors.surface, textSectionTitleColor: colors.muted, monthTextColor: colors.text, dayTextColor: colors.text, todayTextColor: colors.greenBright, textDisabledColor: colors.muted, arrowColor: colors.green, weekVerticalMargin: weekMargin, textMonthFontWeight: "700", textDayFontSize: dense ? 14 : 17, textMonthFontSize: dense ? 18 : 21, textDayHeaderFontSize: dense ? 10 : 12 }} style={[styles.calendar, { height: calendarHeight }]} />
            <View style={{ height: introHeight, gap: 4 }}><Text accessibilityRole="header" numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7} style={[styles.title, { color: colors.text, fontSize: dense ? 26 : compact ? 28 : 32, lineHeight: dense ? 30 : compact ? 34 : 38 }]}>{mt("Как вы себя чувствуете?")}</Text><Text numberOfLines={1} adjustsFontSizeToFit style={[styles.subtitle, { color: colors.muted, fontSize: dense ? 12 : compact ? 14 : 16, lineHeight: dense ? 16 : compact ? 20 : 22 }]}>{mt("Отмечайте состояние каждый день")}</Text></View>
            <View testID="wellbeing-day-card" style={{ height: cardHeight, gap }}>
                <View style={[styles.row, { height: dateHeight }]}>
                    <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8} style={[styles.sectionTitle, { color: colors.text, fontSize: dense ? 18 : 22, flex: 1 }]}>{wellbeingDateLabel(selected)}</Text>
                    <View style={[styles.statusBadge, { backgroundColor: colors.input, maxWidth: "52%" }]}>
                        {loading ? <ActivityIndicator size="small" accessibilityLabel={mt("Загружаем записи")} color={colors.green} /> : null}
                        <Text numberOfLines={1} adjustsFontSizeToFit style={[styles.statusLabel, { color: colors.muted }]}>{statusLabel}</Text>
                    </View>
                </View>
                <View testID="wellbeing-overview" style={{ borderTopWidth: 1, borderColor: colors.border }}>
                    {[0, 1].map(row => <View key={row} style={[styles.metricRow, { height: metricHeight, borderBottomColor: colors.border }]}>
                        {overview.slice(row * 2, row * 2 + 2).map(({ index, icon, level }, column) => <View key={icon} testID={`wellbeing-metric-${icon}`} style={[styles.metricCell, column === 1 ? styles.metricCellRight : null]}>
                            {column === 1 ? <View style={[styles.metricDivider, { backgroundColor: colors.border }]} /> : null}
                            <WellbeingIcon name={icon} level={level} size={dense ? 24 : 32} color={colors.green} />
                            <View style={styles.metricCopy}><Text numberOfLines={1} adjustsFontSizeToFit style={[styles.metricLabel, { color: colors.muted, fontSize: dense ? 12 : 15 }]}>{summary[index][0]}</Text><Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7} style={[styles.metricValue, { color: colors.text, fontSize: dense ? 15 : 18 }]}>{summary[index][1]}</Text></View>
                        </View>)}
                    </View>)}
                </View>
            </View>
        </Body>
        <View testID="wellbeing-action-footer" style={[styles.footer, { height: footerHeight, paddingTop: 0, paddingBottom: 10, gap: 0, backgroundColor: colors.surface, justifyContent: "flex-end" }]}>
            {error ? <Text accessibilityRole="alert" numberOfLines={1} style={[styles.mainError, { color: colors.text }]}>{error}</Text> : null}
            <Pressable accessibilityRole="button" accessibilityLabel={buttonLabel} accessibilityState={{ disabled: !ready && !error || c.busy }} disabled={!ready && !error || c.busy} onPress={() => error ? setRevision(value => value + 1) : open(selected, entry)} style={({ pressed }) => [styles.primary, { backgroundColor: colors.greenBright, opacity: !ready && !error || c.busy ? 0.45 : pressed ? 0.8 : 1 }]}><Text style={styles.primaryLabel}>{buttonLabel}</Text></Pressable>
        </View>
    </View>
}
