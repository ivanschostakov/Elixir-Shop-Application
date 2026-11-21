import { useState } from "react"
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native"
import { mentorText as mt, mentorDateLabel } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { mentorHomeData, mentorHomeNumber as number } from "@/screens/chat/mentor-home-data"
import { MentorNutritionSummary } from "@/screens/chat/mentor-nutrition-summary"
import { MentorQuestionIcon, type MentorQuestionIconName } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { NativeChatAction, nativeChatSettingsActionAvailable } from "@/screens/chat/native-chat-controls"
import { mealGroups, mealLabel, suggestedMeal, waterTarget } from "@/screens/chat/mentor-meals-data"
import type { CompanionEntry, CompanionState, MealType } from "@/services/api/companion"

type Props = {
    state: CompanionState | null; clock: string; animationKey?: number; error?: string; busy: boolean
    onRefresh: () => void; onClose: () => void; onSettings: () => void; onAddFood: (type?: MealType) => void; onNutrition: () => void
    onMeal: (entry: CompanionEntry) => void; onJournal: () => void
    onMealGroup?: (type: MealType, key?: string) => void; onWater?: () => void; onFoodHelp?: (mode: "suggest" | "product") => void
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

function Action({ label, icon, onPress, primary = false, fill = false, compact = false, accent }: { label: string; icon: MentorQuestionIconName; onPress: () => void; primary?: boolean; fill?: boolean; compact?: boolean; accent?: string }) {
    const colors = useMentorPalette()
    return <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={({ pressed }) => [styles.action, compact && { minHeight: 42, paddingVertical: 8 }, fill && { flex: 1 }, { backgroundColor: primary ? accent ?? colors.greenBright : colors.soft, borderColor: primary ? accent ?? colors.greenBright : colors.border, opacity: pressed ? 0.75 : 1 }]}>
        <MentorQuestionIcon name={icon} size={22} color={primary ? "#FFFFFF" : colors.green} /><Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8} style={[styles.actionText, compact && { fontSize: 15, lineHeight: 20 }, { color: primary ? "#FFFFFF" : colors.text }]}>{label}</Text>
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
    const groups = mealGroups(data.meals, clock), currentMeal = suggestedMeal(clock, data.instant)
    const extras = groups.filter(group => group.type === "extra")
    const water = state?.mentor?.today.date === data.date ? state.mentor.today.water?.consumed_ml ?? state.today?.water_ml ?? 0 : 0
    const waterGoal = waterTarget(state)
    const remaining = data.remaining === null ? mt("Ориентир питания не задан") : data.remaining >= 0 ? mt("Осталось {0} ккал", [number(data.remaining)]) : mt("Сверх ориентира {0} ккал", [number(-data.remaining)])
    return <View testID="mentor-home" style={[styles.screen, { backgroundColor: colors.surface }]}>
        <MentorHomeHeader onBack={props.onClose} onSettings={props.onSettings} />
        <View testID="mentor-home-content" onLayout={event => setHeight(event.nativeEvent.layout.height)} style={[styles.body, { gap: dense ? 3 : compact ? 6 : 8, paddingHorizontal: dense ? 18 : 24, paddingBottom: dense ? 4 : 8, paddingTop: dense ? 2 : 5 }]}>
            <View style={[styles.today, dense && { flexDirection: "row", justifyContent: "space-between", alignItems: "center" }]}><Text accessibilityRole="header" style={[styles.title, { color: colors.text, fontSize: dense ? 26 : 32, lineHeight: dense ? 32 : 38 }]}>{mt("Сегодня")}</Text><Text style={[styles.date, { color: colors.muted }, dense && { fontSize: 12, lineHeight: 18 }]}>{date.charAt(0).toUpperCase() + date.slice(1)}</Text></View>
            {props.error ? <Pressable accessibilityRole="button" accessibilityLabel={mt("Обновить данные")} onPress={props.onRefresh} style={[styles.notice, { backgroundColor: colors.soft }]}><Text accessibilityRole="alert" style={{ color: colors.text }}>{props.error}</Text><Text style={{ color: colors.green }}>{mt("Обновить данные")}</Text></Pressable> : null}
            <MentorNutritionSummary consumed={data.consumed} target={data.target} remaining={remaining} water={water} waterGoal={waterGoal} animationKey={`${data.date}:${props.animationKey ?? 0}`} dense={dense} compact={compact} onNutrition={props.onNutrition} onWater={props.onWater} />
            <Action label={mt("Добавить {0}", [mealLabel(currentMeal).toLowerCase()])} icon="food" primary compact={dense} onPress={() => props.onAddFood(currentMeal)} />
            <View style={{ gap: dense ? 0 : 3 }}>
                <View style={[styles.sectionHeader, dense && { minHeight: 28, marginBottom: 2 }]}><Text accessibilityRole="header" style={[styles.sectionTitle, { color: colors.text }, dense && { fontSize: 20, lineHeight: 24 }]}>{mt("Приёмы пищи")}</Text><Pressable accessibilityRole="button" onPress={props.onJournal} hitSlop={8}><Text style={[styles.subtitle, { color: colors.green }]}>{mt("Все записи")}</Text></Pressable></View>
                {groups.slice(0, 3).map(group => <Pressable key={group.type} accessibilityRole="button" accessibilityLabel={`${mealLabel(group.type)}, ${number(group.total.kcal)} ${mt("ккал")}`} onPress={() => group.entries.length ? props.onMealGroup ? props.onMealGroup(group.type) : props.onMeal(group.entries[0]) : props.onAddFood(group.type)}
                    style={({ pressed }) => [styles.mealRow, { minHeight: dense ? 34 : compact ? 45 : 51, borderBottomColor: colors.border, backgroundColor: group.type === currentMeal && !group.entries.length ? colors.soft : "transparent", opacity: pressed ? 0.7 : 1 }]}>
                    <MentorQuestionIcon name={group.entries.length ? "check" : "plus"} size={dense ? 18 : 22} color={colors.green} />
                    <View style={styles.rowCopy}><Text style={[styles.rowTitle, { color: colors.text, fontSize: dense ? 14 : 16, lineHeight: dense ? 19 : 23 }]}>{mealLabel(group.type)}</Text>{!dense ? <Text numberOfLines={1} style={[styles.subtitle, { color: colors.muted, fontSize: 12 }]}>{group.entries.map(entry => entry.data.name).join(", ") || mt("Пока не добавлен")}</Text> : null}</View>
                    <Text style={[styles.trailing, { color: group.entries.length ? colors.text : colors.green }]}>{group.entries.length ? mt("{0} ккал", [number(group.total.kcal)]) : mt("Добавить")}</Text><MentorQuestionIcon name="chevronRight" size={17} color={colors.muted} />
                </Pressable>)}
            </View>
            <Pressable accessibilityRole="button" accessibilityLabel={mt("Ещё приём пищи")} onPress={() => extras.length && props.onMealGroup ? props.onMealGroup("extra") : props.onAddFood("extra")} style={({ pressed }) => [styles.extraMeal, { minHeight: dense ? 34 : 44, opacity: pressed ? 0.65 : 1 }]}>
                <MentorQuestionIcon name="plus" size={21} color={colors.green} /><Text style={[styles.extraLabel, { color: colors.green, fontSize: dense ? 14 : 16 }]}>{mt("Ещё приём пищи")}</Text>
                {extras.length ? <Text style={[styles.trailing, { color: colors.muted }]}>{extras.length}</Text> : null}<MentorQuestionIcon name="chevronRight" size={17} color={colors.muted} />
            </Pressable>
            <View testID="mentor-food-help" style={[styles.helpPanel, { backgroundColor: colors.soft }]}>
                {([["suggest", "Что поесть?", "food"], ["product", "О продукте", "search"]] as const).map(([mode, label, icon], index) => <Pressable key={mode} accessibilityRole="button" accessibilityLabel={mt(label)} onPress={() => props.onFoodHelp?.(mode)} style={({ pressed }) => [styles.helpItem, { minHeight: dense ? 58 : compact ? 70 : 80, opacity: pressed ? 0.65 : 1 }, index > 0 && { borderLeftWidth: StyleSheet.hairlineWidth, borderLeftColor: colors.border }]}>
                    <MentorQuestionIcon name={icon} size={dense ? 22 : 25} color={colors.green} /><Text numberOfLines={1} adjustsFontSizeToFit style={[styles.helpLabel, { color: colors.text, fontSize: dense ? 13 : 15 }]}>{mt(label)}</Text>
                </Pressable>)}
            </View>
        </View>
    </View>
}

export const mentorHomeStyles = StyleSheet.create({ body: { width: "100%", maxWidth: 560, alignSelf: "center", paddingHorizontal: 24, paddingTop: 14, paddingBottom: 20, gap: 12 } })
const styles = StyleSheet.create({
    screen: { flex: 1 }, header: { minHeight: 56, flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 16, paddingBottom: 6 }, iconButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
    brand: { flex: 1, flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 7 }, brandName: { fontSize: 22, fontWeight: "800", flexShrink: 1, letterSpacing: -0.5 }, headerTitle: { flex: 1, fontSize: 22, fontWeight: "700", textAlign: "center" },
    body: { ...mentorHomeStyles.body, flex: 1, paddingBottom: 8 }, today: { gap: 4 }, title: { fontSize: 32, lineHeight: 38, fontWeight: "800", letterSpacing: -0.8 }, date: { fontWeight: "500", fontSize: 16, lineHeight: 22 },
    action: { minHeight: 46, flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 9, borderWidth: 1, borderRadius: 16, paddingHorizontal: 12, paddingVertical: 12 }, actionText: { fontSize: 17, lineHeight: 23, fontWeight: "700", flexShrink: 1 },
    sectionHeader: { minHeight: 33, flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }, sectionTitle: { fontSize: 24, lineHeight: 30, fontWeight: "800", letterSpacing: -0.5 },
    rowCopy: { flex: 1, minWidth: 0, gap: 3 }, rowTitle: { fontSize: 17, lineHeight: 23, fontWeight: "700" }, subtitle: { fontWeight: "500", fontSize: 14, lineHeight: 19 }, trailing: { fontWeight: "600", fontSize: 14, lineHeight: 20, flexShrink: 1, textAlign: "right" },
    mealRow: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 7, borderRadius: 13, borderBottomWidth: StyleSheet.hairlineWidth }, extraMeal: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 7 }, extraLabel: { flex: 1, fontWeight: "700", lineHeight: 22 },
    helpPanel: { flexDirection: "row", borderRadius: 20, paddingVertical: 6, marginTop: 2 }, helpItem: { flex: 1, alignItems: "center", justifyContent: "center", gap: 7, paddingHorizontal: 10 }, helpLabel: { fontWeight: "700", lineHeight: 21 },
    notice: { borderRadius: 14, padding: 14, gap: 8 },
})
