import { useLayoutEffect, useRef, useState } from "react"
import { Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useChatReducedMotion } from "@/screens/chat/chat-mode-transition"
import { mentorHomeNumber as number } from "@/screens/chat/mentor-home-data"
import { MentorCalorieRing, MentorMacroProgress } from "@/screens/chat/mentor-nutrition-progress"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import type { Nutrition } from "@/services/api/companion"

export type NutritionMetric = "nutrition" | "water"

export function MentorNutritionPager({ active, onSelect, consumed, target, remaining, water, waterGoal, animationKey, dense, compact, onNutrition }: {
    active: NutritionMetric; onSelect: (metric: NutritionMetric) => void; consumed: Nutrition | null; target: Nutrition | null; remaining: string
    water: number; waterGoal: number; animationKey: string; dense: boolean; compact: boolean; onNutrition: () => void
}) {
    const colors = useMentorPalette(), reduced = useChatReducedMotion()
    const window = useWindowDimensions()
    const [width, setWidth] = useState(Math.min(window.width, 560) - (dense ? 36 : 48))
    const scroll = useRef<ScrollView>(null), selected = useRef(active); selected.current = active
    const peek = dense ? 28 : 34, step = Math.max(200, width - peek)
    useLayoutEffect(() => { scroll.current?.scrollTo({ x: selected.current === "water" ? step : 0, animated: false }) }, [step])
    const select = (metric: NutritionMetric) => {
        onSelect(metric)
        scroll.current?.scrollTo({ x: metric === "water" ? step : 0, animated: !reduced })
    }
    return <View testID="mentor-nutrition-pager" onLayout={event => setWidth(event.nativeEvent.layout.width)}>
        <ScrollView ref={scroll} horizontal showsHorizontalScrollIndicator={false} bounces={false} decelerationRate="fast" disableIntervalMomentum snapToOffsets={[0, step]} scrollEventThrottle={32}
            onMomentumScrollEnd={event => onSelect(event.nativeEvent.contentOffset.x >= step / 2 ? "water" : "nutrition")}
            contentContainerStyle={{ paddingRight: peek }} style={styles.viewport}>
            <View testID="mentor-metric-nutrition" accessibilityElementsHidden={active !== "nutrition"} importantForAccessibility={active === "nutrition" ? "auto" : "no-hide-descendants"} style={[styles.page, { width: step, paddingRight: 17, gap: dense ? 4 : compact ? 8 : 12 }]}>
                <View style={[styles.calories, { gap: dense ? 12 : 16 }]}>
                    <MentorCalorieRing key={animationKey} amount={consumed?.kcal} target={target?.kcal} label={mt("Калории за сегодня")} size={dense ? 50 : compact ? 64 : 76} />
                    <View style={{ flex: 1, gap: dense ? 3 : 7 }}><Text accessibilityLabel={mt("Калории за сегодня")} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.65} style={[styles.value, { color: colors.text, fontSize: dense ? 20 : 24 }]}>{number(consumed?.kcal)}{target ? ` / ${number(target.kcal)}` : ""}<Text style={styles.unit}> {mt("ккал")}</Text></Text>
                        <Pressable accessibilityRole="button" accessibilityLabel={!target ? mt("Настроить питание") : remaining} onPress={onNutrition}><Text style={[styles.remaining, { color: colors.muted, fontSize: dense ? 12 : 15 }]}>{remaining}</Text></Pressable>
                    </View>
                </View>
                {(["protein", "fat", "carbs"] as const).map((key, index) => <View key={key} style={styles.macroRow}>
                    <Text style={[styles.macroLabel, { color: colors.text, width: dense ? 75 : 83, fontSize: dense ? 12 : 14 }]}>{[mt("Белки"), mt("Жиры"), mt("Углеводы")][index]}</Text>
                    <MentorMacroProgress key={`${animationKey}:${key}`} amount={consumed?.[key]} target={target?.[key]} index={index} label={[mt("Белки"), mt("Жиры"), mt("Углеводы")][index]} />
                    <Text numberOfLines={1} adjustsFontSizeToFit style={[styles.macroValue, { color: colors.text, width: dense ? 82 : 96, fontSize: dense ? 12 : 14 }]}>{number(consumed?.[key])}{target ? ` / ${number(target[key])}` : ""} {mt("г")}</Text>
                </View>)}
            </View>
            <Pressable testID="mentor-metric-water" accessibilityElementsHidden={active !== "water"} importantForAccessibility={active === "water" ? "auto" : "no-hide-descendants"} onPress={() => { if (active !== "water") select("water") }} style={[styles.page, styles.waterPage, { width: step, paddingRight: 14 }]}>
                <MentorCalorieRing key={`${animationKey}:water`} kind="water" amount={water} target={waterGoal} label={mt("Вода за сегодня")} size={dense ? 86 : 108} />
                <View style={{ flex: 1, gap: 8 }}><Text style={[styles.waterTitle, { color: colors.blue }]}>{mt("Вода")}</Text><Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.65} style={[styles.value, { color: colors.text, fontSize: dense ? 22 : 26 }]}>{number(water)}<Text style={styles.unit}> / {number(waterGoal)} {mt("мл")}</Text></Text><Text style={[styles.remaining, { color: colors.muted }]}>{water < waterGoal ? mt("Осталось {0} мл", [number(waterGoal - water)]) : mt("Дневной ориентир достигнут")}</Text></View>
            </Pressable>
        </ScrollView>
        <View accessibilityRole="tablist" accessibilityLabel={mt("Показатели за день")} style={styles.dots}>{(["nutrition", "water"] as const).map(metric => <Pressable key={metric} accessibilityRole="tab" accessibilityLabel={metric === "water" ? mt("Вода") : mt("Питание")} accessibilityState={{ selected: active === metric }} onPress={() => select(metric)} hitSlop={12} style={styles.dotButton}><View style={{ width: active === metric ? 18 : 5, height: 5, borderRadius: 3, backgroundColor: active === metric ? metric === "water" ? colors.blue : colors.greenBright : colors.border }} /></Pressable>)}</View>
    </View>
}

const styles = StyleSheet.create({
    viewport: { flexGrow: 0 }, page: { paddingVertical: 4 }, calories: { flexDirection: "row", alignItems: "center", marginBottom: 1 }, value: { fontWeight: "800", letterSpacing: -0.6 }, unit: { fontSize: 14, fontWeight: "600" }, remaining: { fontSize: 14, lineHeight: 20, fontWeight: "500" }, macroRow: { flexDirection: "row", alignItems: "center", gap: 7 }, macroLabel: { lineHeight: 20, fontWeight: "700" }, macroValue: { textAlign: "right", lineHeight: 20, fontWeight: "600" }, waterPage: { flexDirection: "row", gap: 16, alignItems: "center", justifyContent: "center" }, waterTitle: { fontSize: 20, fontWeight: "800" }, dots: { flexDirection: "row", justifyContent: "center", alignItems: "center", height: 18, gap: 1 }, dotButton: { minWidth: 30, height: 18, justifyContent: "center", alignItems: "center" },
})
