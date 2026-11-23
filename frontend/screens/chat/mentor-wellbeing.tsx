import { useCallback, useEffect, useRef, useState } from "react"
import { ActivityIndicator, Pressable, Text, View, useWindowDimensions } from "react-native"
import { LocaleConfig, type CalendarProps } from "react-native-calendars"
import { AppCalendar } from "@/components/platform/app-calendar"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { MentorHomeHeader } from "@/screens/chat/mentor-home"
import { calendarDate } from "@/screens/chat/companion-timezones"
import type { useCompanion } from "@/screens/chat/companion"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { getCompanionEntries, type CompanionEntry } from "@/services/api/companion"
import { getErrorMessage } from "@/utils/errors"
import { loadWellbeingMonth, sleepDurationLabel, wellbeingDateLabel, wellbeingDays, wellbeingDraft, wellbeingLabels } from "@/screens/chat/mentor-wellbeing-data"
import { WellbeingIcon } from "@/screens/chat/mentor-wellbeing-icons"
import { wellbeingStyles as styles } from "@/screens/chat/mentor-wellbeing.styles"

type Controller = ReturnType<typeof useCompanion>
const months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
const weekdays = ["Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
const shortWeekdays = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]

export function MentorWellbeingScreen({ controller: c, active, onClose, onSettings }: { controller: Controller; active: boolean; onClose: () => void; onSettings: () => void }) {
    const { language } = useLanguage()
    const { isDark } = useTheme()
    const colors = useMentorPalette()
    const today = calendarDate()
    const window = useWindowDimensions()
    const [height, setHeight] = useState(Math.max(360, window.height - 160))
    const dense = height < 560
    const compact = height < 680
    const weekMargin = dense ? 0 : compact ? 2 : 6
    const cardHeight = dense ? 78 : 100
    const calendarRoom = height - 56 - (dense ? 64 : 80) - cardHeight - (dense ? 62 : 74) - (dense ? 30 : 56)
    const daySize = Math.max(20, Math.min(40, Math.floor((calendarRoom - 80) / 6 - weekMargin * 2)))
    const calendarHeight = 80 + 6 * (daySize + weekMargin * 2)
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
    if (active) {
        LocaleConfig.locales[`wellbeing-${language}`] = { monthNames: months.map(name => mt(name)), monthNamesShort: months.map(name => mt(name)), dayNames: weekdays.map(name => mt(name)), dayNamesShort: shortWeekdays.map(name => mt(name)), today: mt("Сегодня") }
        LocaleConfig.defaultLocale = `wellbeing-${language}`
    }
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
    const summary = entry ? wellbeingDraft(entry.data) : null
    const buttonLabel = error ? mt("Попробовать ещё раз") : entry ? mt("Изменить запись") : mt("Заполнить анкету")
    return <View testID="mentor-wellbeing" onLayout={event => setHeight(event.nativeEvent.layout.height)} style={[styles.screen, { backgroundColor: colors.surface }]}>
        <MentorHomeHeader title={mt("Самочувствие")} onBack={onClose} onSettings={onSettings} />
        <View style={{ flex: 1, minHeight: 0, width: "100%", maxWidth: 560, alignSelf: "center", paddingHorizontal: 24, paddingTop: dense ? 4 : 10, paddingBottom: 8, gap: dense ? 6 : 12 }}>
            <AppCalendar key={`${language}|${isDark}|${daySize}|${weekMargin}`} current={`${month}-01`} maxDate={today} firstDay={1} hideExtraDays disableMonthChange disableAllTouchEventsForDisabledDays disableArrowRight={month >= today.slice(0, 7)} disabledByDefault={!ready}
                markedDates={marks} onMonthChange={date => {
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
            <View style={{ gap: 5 }}><Text accessibilityRole="header" numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75} style={[styles.title, { color: colors.text, fontSize: dense ? 28 : 32 }]}>{mt("Как вы себя чувствуете?")}</Text><Text style={[styles.subtitle, { color: colors.muted, fontSize: dense ? 13 : 16, lineHeight: dense ? 18 : 22 }]}>{mt("Отмечайте состояние каждый день")}</Text></View>
            <View testID="wellbeing-day-card" style={[styles.card, { height: cardHeight, backgroundColor: colors.surface, paddingHorizontal: 0, paddingVertical: dense ? 6 : 10, gap: dense ? 8 : 12 }]}>
                <View style={styles.row}><Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8} style={[styles.sectionTitle, { color: colors.text, fontSize: dense ? 18 : 20, flex: 1 }]}>{wellbeingDateLabel(selected)}{!loading && !error && !entry ? ` (${mt("Пока нет записи").toLocaleLowerCase()})` : ""}</Text><View style={{ width: 20, height: 20 }}>{loading ? <ActivityIndicator accessibilityLabel={mt("Загружаем записи")} color={colors.greenBright} /> : null}</View></View>
                {error ? <Text accessibilityRole="alert" numberOfLines={2} style={{ color: colors.text, fontSize: 12, lineHeight: 14 }}>{error}</Text> : entry && summary ? <View style={[styles.row, { justifyContent: "flex-start" }]}>
                    <WellbeingIcon name="face" level={summary.wellbeing ?? 3} size={dense ? 28 : 38} color={colors.green} />
                    <View style={{ flex: 1, gap: 2 }}><Text numberOfLines={1} style={{ color: colors.text, fontWeight: "700", fontSize: dense ? 15 : 17 }}>{summary.wellbeing == null ? mt("Ваша запись") : mt(wellbeingLabels[summary.wellbeing - 1])}</Text>
                        {!dense ? <Text numberOfLines={1} adjustsFontSizeToFit style={{ color: colors.muted, fontSize: 13 }}>{mt("Энергия")} {summary.energy == null ? "—" : mt("{0} из 5", [summary.energy])} · {mt("Сон")} {sleepDurationLabel(summary.sleepMinutes)}</Text> : null}</View>
                </View> : null}
            </View>
        </View>
        <View testID="wellbeing-action-footer" style={[styles.footer, { paddingBottom: 10, backgroundColor: colors.surface }]}>
            <Pressable accessibilityRole="button" accessibilityLabel={buttonLabel} accessibilityState={{ disabled: !ready && !error || c.busy }} disabled={!ready && !error || c.busy} onPress={() => error ? setRevision(value => value + 1) : open(selected, entry)} style={({ pressed }) => [styles.primary, { backgroundColor: colors.greenBright, opacity: !ready && !error || c.busy ? 0.45 : pressed ? 0.8 : 1 }]}><Text style={styles.primaryLabel}>{buttonLabel}</Text></Pressable>
        </View>
    </View>
}
