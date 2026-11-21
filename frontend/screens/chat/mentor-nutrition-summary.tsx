import { Pressable, StyleSheet, Text, View } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { mentorHomeNumber as number } from "@/screens/chat/mentor-home-data"
import { MentorCalorieRing, MentorMacroProgress } from "@/screens/chat/mentor-nutrition-progress"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import type { Nutrition } from "@/services/api/companion"

export function MentorNutritionSummary({ consumed, target, remaining, water, waterGoal, animationKey, dense, compact, onNutrition, onWater }: {
    consumed: Nutrition | null; target: Nutrition | null; remaining: string; water: number; waterGoal: number
    animationKey: string; dense: boolean; compact: boolean; onNutrition: () => void; onWater?: () => void
}) {
    const colors = useMentorPalette()
    const labelStyle = [styles.label, { color: colors.text, width: dense ? 75 : 83, fontSize: dense ? 12 : 14 }]
    const valueStyle = [styles.amount, { color: colors.text, width: dense ? 110 : 124, fontSize: dense ? 12 : 14 }]
    return <View testID="mentor-nutrition-summary" style={[styles.summary, { gap: dense ? 4 : compact ? 8 : 12 }]}>
        <View style={[styles.calories, { gap: dense ? 12 : 16 }]}>
            <MentorCalorieRing key={animationKey} amount={consumed?.kcal} target={target?.kcal} label={mt("Калории за сегодня")} size={dense ? 50 : compact ? 64 : 76} />
            <View style={{ flex: 1, gap: dense ? 3 : 7 }}><Text accessibilityLabel={mt("Калории за сегодня")} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.65} style={[styles.value, { color: colors.text, fontSize: dense ? 20 : 24 }]}>{number(consumed?.kcal)}{target ? ` / ${number(target.kcal)}` : ""}<Text style={styles.unit}> {mt("ккал")}</Text></Text>
                <Pressable accessibilityRole="button" accessibilityLabel={!target ? mt("Настроить питание") : remaining} onPress={onNutrition}><Text style={[styles.remaining, { color: colors.muted, fontSize: dense ? 12 : 15 }]}>{remaining}</Text></Pressable>
            </View>
        </View>
        {(["protein", "fat", "carbs"] as const).map((key, index) => <View key={key} style={styles.row}>
            <Text style={labelStyle}>{[mt("Белки"), mt("Жиры"), mt("Углеводы")][index]}</Text>
            <MentorMacroProgress key={`${animationKey}:${key}`} amount={consumed?.[key]} target={target?.[key]} index={index} label={[mt("Белки"), mt("Жиры"), mt("Углеводы")][index]} />
            <Text numberOfLines={1} adjustsFontSizeToFit style={valueStyle}>{number(consumed?.[key])}{target ? ` / ${number(target[key])}` : ""} {mt("г")}</Text>
        </View>)}
        <Pressable testID="mentor-water-row" accessibilityRole="button" accessibilityLabel={mt("Вода — {0} / {1} мл", [number(water), number(waterGoal)])} accessibilityHint={mt("Добавить воду")} onPress={onWater} style={styles.row}>
            <Text style={labelStyle}>{mt("Вода")}</Text>
            <MentorMacroProgress key={`${animationKey}:water`} amount={water} target={waterGoal} index={3} label={mt("Вода")} color={colors.blue} />
            <Text numberOfLines={1} adjustsFontSizeToFit style={valueStyle}>{number(water)} / {number(waterGoal)} {mt("мл")}</Text>
        </Pressable>
    </View>
}

const styles = StyleSheet.create({
    summary: { width: "100%", paddingVertical: 4 }, calories: { flexDirection: "row", alignItems: "center", marginBottom: 1 }, value: { fontWeight: "800", letterSpacing: -0.6 }, unit: { fontSize: 14, fontWeight: "600" }, remaining: { fontSize: 14, lineHeight: 20, fontWeight: "500" }, row: { flexDirection: "row", alignItems: "center", gap: 7 }, label: { lineHeight: 20, fontWeight: "700" }, amount: { textAlign: "right", lineHeight: 20, fontWeight: "600" },
})
