import { useState } from "react"
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native"
import { mentorText as mt, mentorDateLabel } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { formatCompanionDate } from "@/screens/chat/companion-timezones"
import { mentorHomeData, mentorHomeNumber as number } from "@/screens/chat/mentor-home-data"
import { MentorCalorieRing, MentorMacroProgress } from "@/screens/chat/mentor-nutrition-progress"
import { MentorQuestionIcon, type MentorQuestionIconName } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { NativeChatAction, nativeChatSettingsActionAvailable } from "@/screens/chat/native-chat-controls"
import type { CompanionEntry, CompanionState } from "@/services/api/companion"

type Props = {
    state: CompanionState | null; clock: string; animationKey?: number; error?: string; busy: boolean
    onRefresh: () => void; onClose: () => void; onSettings: () => void; onAddFood: () => void; onNutrition: () => void
    onMeal: (entry: CompanionEntry) => void; onJournal: () => void
}

export function MentorHomeHeader({ onBack, onSettings, title, backLabel }: { onBack: () => void; onSettings?: () => void; title?: string; backLabel?: string }) {
    const colors = useMentorPalette()
    const { isDark } = useTheme()
    const label = backLabel ?? (title ? mt("Назад") : mt("На главную магазина"))
    return <View style={styles.header}>
        {NativeChatAction ? <NativeChatAction action="back" dark={isDark} label={label} onAction={onBack} style={styles.iconButton} /> :
            <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onBack} style={styles.iconButton}><MentorQuestionIcon name="back" size={24} color={colors.text} /></Pressable>}
        {title ? <Text accessibilityRole="header" style={[styles.headerTitle, { color: colors.text }]}>{title}</Text> :
            <View style={styles.brand}><MentorQuestionIcon name="leaf" size={27} color={colors.green} /><Text accessibilityRole="header" numberOfLines={1} adjustsFontSizeToFit style={[styles.brandName, { color: colors.text }]}>{mt("Наставник")}</Text></View>}
        {onSettings ? NativeChatAction && nativeChatSettingsActionAvailable ? <NativeChatAction action="settings" dark={isDark} label={mt("Настройки наставника")} onAction={onSettings} style={styles.iconButton} /> :
            <Pressable accessibilityRole="button" accessibilityLabel={mt("Настройки наставника")} onPress={onSettings} style={[styles.iconButton, { backgroundColor: colors.soft, borderRadius: 22 }]}><MentorQuestionIcon name="settings" size={23} color={colors.green} /></Pressable> : <View style={styles.iconButton} />}
    </View>
}

function Action({ label, icon, onPress, primary = false, fill = false }: { label: string; icon: MentorQuestionIconName; onPress: () => void; primary?: boolean; fill?: boolean }) {
    const colors = useMentorPalette()
    return <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={({ pressed }) => [styles.action, fill && { flex: 1 }, { backgroundColor: primary ? colors.greenBright : colors.soft, borderColor: primary ? colors.greenBright : colors.border, opacity: pressed ? 0.75 : 1 }]}>
        <MentorQuestionIcon name={icon} size={22} color={primary ? "#FFFFFF" : colors.green} /><Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8} style={[styles.actionText, { color: primary ? "#FFFFFF" : colors.text }]}>{label}</Text>
    </Pressable>
}

function DayRow({ title, subtitle, done, trailing, onPress, skipped = false }: { title: string; subtitle?: string; done?: boolean; trailing?: string; onPress: () => void; skipped?: boolean }) {
    const colors = useMentorPalette()
    return <Pressable accessibilityRole="button" accessibilityLabel={[title, subtitle, trailing].filter(Boolean).join(", ")} onPress={onPress} style={({ pressed }) => [styles.dayRow, { borderBottomColor: colors.border, opacity: pressed ? 0.65 : 1 }]}>
        <View style={[styles.status, { borderColor: done ? colors.green : colors.muted, backgroundColor: done ? colors.mint : "transparent" }]}>{done ? <MentorQuestionIcon name="check" size={17} color={colors.green} /> : skipped ? <Text style={{ color: colors.muted }}>−</Text> : null}</View>
        <View style={styles.rowCopy}><Text numberOfLines={1} style={[styles.rowTitle, { color: colors.text }]}>{title}</Text>{subtitle ? <Text numberOfLines={1} style={[styles.subtitle, { color: colors.muted }]}>{subtitle}</Text> : null}</View>
        {trailing ? <Text style={[styles.trailing, { color: colors.text }]}>{trailing}</Text> : null}<MentorQuestionIcon name="chevronRight" size={19} color={colors.muted} />
    </Pressable>
}

export function MentorHomeScreen(props: Props) {
    useLanguage()
    const colors = useMentorPalette()
    const { state, clock } = props
    const data = mentorHomeData(state, clock)
    const window = useWindowDimensions()
    const [height, setHeight] = useState(window.height - 150)
    const compact = height < 650, dense = height < 560
    const date = mentorDateLabel(new Date(`${data.date}T12:00:00`), dense ? { day: "numeric", month: "short" } : { weekday: "long", day: "numeric", month: "long" })
    const mealLimit = Math.max(1, Math.min(6, Math.floor((height - (dense ? 370 : 440)) / 54)))
    const time = (value: string) => formatCompanionDate(value, clock).match(/(\d{2}:\d{2})(?::\d{2})?/)?.[1] ?? ""
    const remaining = data.remaining === null ? mt("Ориентир питания не задан") : data.remaining >= 0 ? mt("Осталось {0} ккал", [number(data.remaining)]) : mt("Сверх ориентира {0} ккал", [number(-data.remaining)])
    return <View testID="mentor-home" style={[styles.screen, { backgroundColor: colors.surface }]}>
        <MentorHomeHeader onBack={props.onClose} onSettings={props.onSettings} />
        <View testID="mentor-home-content" onLayout={event => setHeight(event.nativeEvent.layout.height)} style={[styles.body, { gap: dense ? 6 : compact ? 8 : 12, paddingTop: dense ? 4 : 8 }]}>
            <View style={[styles.today, dense && { flexDirection: "row", justifyContent: "space-between", alignItems: "center" }]}><Text accessibilityRole="header" style={[styles.title, { color: colors.text, fontSize: dense ? 28 : 32 }]}>{mt("Сегодня")}</Text><Text style={[styles.date, { color: colors.muted }]}>{date.charAt(0).toUpperCase() + date.slice(1)}</Text></View>
            {props.error ? <Pressable accessibilityRole="button" accessibilityLabel={mt("Обновить данные")} onPress={props.onRefresh} style={[styles.notice, { backgroundColor: colors.soft }]}><Text accessibilityRole="alert" style={{ color: colors.text }}>{props.error}</Text><Text style={{ color: colors.green }}>{mt("Обновить данные")}</Text></Pressable> : null}
            <View style={[styles.nutrition, { gap: dense ? 6 : compact ? 8 : 12 }]}>
                <View style={styles.calories}>
                    <MentorCalorieRing key={`${data.date}:${props.animationKey ?? 0}`} amount={data.consumed?.kcal} target={data.target?.kcal} label={mt("Калории за сегодня")} size={dense ? 64 : 80} />
                    <View style={styles.calorieCopy}><Text accessibilityLabel={mt("Калории за сегодня")} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7} style={[styles.calorieValue, { color: colors.text }]}>{number(data.consumed?.kcal)}{data.target ? ` / ${number(data.target.kcal)}` : ""}<Text style={styles.calorieUnit}> {mt("ккал")}</Text></Text>
                        <Pressable accessibilityRole="button" accessibilityLabel={!data.target ? mt("Настроить питание") : remaining} onPress={props.onNutrition}><Text style={[styles.remaining, { color: colors.muted }]}>{remaining}</Text></Pressable>
                    </View>
                </View>
                {(["protein", "fat", "carbs"] as const).map((key, index) => <View key={key} style={styles.macroRow}>
                    <Text style={[styles.macroLabel, { color: colors.text }]}>{[mt("Белки"), mt("Жиры"), mt("Углеводы")][index]}</Text>
                    <MentorMacroProgress key={`${data.date}:${props.animationKey ?? 0}:${key}`} amount={data.consumed?.[key]} target={data.target?.[key]} index={index} label={[mt("Белки"), mt("Жиры"), mt("Углеводы")][index]} />
                    <Text numberOfLines={1} adjustsFontSizeToFit style={[styles.macroValue, { color: colors.text }]}>{number(data.consumed?.[key])}{data.target ? ` / ${number(data.target[key])}` : ""} {mt("г")}</Text>
                </View>)}
            </View>
            <Action label={mt("Добавить еду")} icon="food" primary onPress={props.onAddFood} />
            <View>
                <View style={styles.sectionHeader}><Text accessibilityRole="header" style={[styles.sectionTitle, { color: colors.text }]}>{mt("Ваш день")}</Text><Pressable accessibilityRole="button" onPress={props.onJournal} hitSlop={8}><Text style={[styles.subtitle, { color: colors.green }]}>{mt("Все записи")}</Text></Pressable></View>
                {mealLimit > 0 ? data.meals.slice(-mealLimit).map(entry => <DayRow key={entry.id} title={entry.data.name || mt("Приём пищи")} subtitle={dense ? undefined : time(entry.occurred_at)} done trailing={entry.data.nutrition ? mt("{0} ккал", [number(entry.data.nutrition.kcal)]) : undefined} onPress={() => props.onMeal(entry)} />) : null}
                {!data.meals.length && !dense ? <Text style={[styles.empty, { color: colors.muted }]}>{mt("Добавьте первый приём пищи")}</Text> : null}
            </View>
        </View>
    </View>
}

export const mentorHomeStyles = StyleSheet.create({ body: { width: "100%", maxWidth: 560, alignSelf: "center", paddingHorizontal: 24, paddingTop: 14, paddingBottom: 20, gap: 12 } })
const styles = StyleSheet.create({
    screen: { flex: 1 }, header: { minHeight: 56, flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 16, paddingBottom: 6 }, iconButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
    brand: { flex: 1, flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 7 }, brandName: { fontSize: 22, fontWeight: "800", flexShrink: 1, letterSpacing: -0.5 }, headerTitle: { flex: 1, fontSize: 22, fontWeight: "700", textAlign: "center" },
    body: { ...mentorHomeStyles.body, flex: 1, paddingBottom: 8 }, today: { gap: 4 }, title: { fontSize: 32, lineHeight: 38, fontWeight: "800", letterSpacing: -0.8 }, date: { fontWeight: "500", fontSize: 16, lineHeight: 22 },
    nutrition: { gap: 12, paddingVertical: 4 }, calories: { flexDirection: "row", gap: 19, alignItems: "center", marginBottom: 1 }, calorieCopy: { flex: 1, gap: 7 }, calorieValue: { fontSize: 24, lineHeight: 30, fontWeight: "800", letterSpacing: -0.6 }, calorieUnit: { fontSize: 17, fontWeight: "700" }, remaining: { fontWeight: "500", fontSize: 16, lineHeight: 22 },
    macroRow: { flexDirection: "row", gap: 12, alignItems: "center" }, macroLabel: { width: 89, fontSize: 15, lineHeight: 21, fontWeight: "700" }, macroValue: { fontWeight: "600", width: 104, textAlign: "right", fontSize: 15, lineHeight: 21 },
    action: { minHeight: 46, flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 9, borderWidth: 1, borderRadius: 16, paddingHorizontal: 12, paddingVertical: 12 }, actionText: { fontSize: 17, lineHeight: 23, fontWeight: "700", flexShrink: 1 },
    sectionHeader: { minHeight: 33, flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }, sectionTitle: { fontSize: 24, lineHeight: 30, fontWeight: "800", letterSpacing: -0.5 },
    dayRow: { minHeight: 50, flexDirection: "row", alignItems: "center", gap: 11, paddingVertical: 6, borderBottomWidth: StyleSheet.hairlineWidth }, status: { width: 23, height: 23, borderWidth: 1.5, borderRadius: 12, alignItems: "center", justifyContent: "center" }, rowCopy: { flex: 1, minWidth: 0, gap: 3 }, rowTitle: { fontSize: 17, lineHeight: 23, fontWeight: "700" }, subtitle: { fontWeight: "500", fontSize: 14, lineHeight: 19 }, trailing: { fontWeight: "600", fontSize: 14, lineHeight: 20, flexShrink: 1, textAlign: "right" }, empty: { fontWeight: "500", fontSize: 14, lineHeight: 20, paddingVertical: 6 },
    notice: { borderRadius: 14, padding: 14, gap: 8 },
})
