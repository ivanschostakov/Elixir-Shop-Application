import { StyleSheet, Text, View } from "react-native"
import { mentorText as mt, mentorLocale } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { MentorFlowBody, MentorFlowButton, MentorFlowHeader, flowStyles } from "@/screens/chat/mentor-onboarding-layout"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { MentorQuestionIcon } from "@/screens/chat/mentor-question-icon"
import type { CompanionState } from "@/services/api/companion"

export function MentorNutritionResult({ state, onContinue, onDecline, onBack, onClose }: { state: CompanionState | null; onContinue: () => void; onDecline: () => void; onBack: () => void; onClose: () => void }) {
    useLanguage()
    const colors = useMentorPalette()
    const profile = state?.profile?.data
    const nutrition = profile?.onboarding_nutrition_reason ? null : profile?.nutrition
    const number = (value: string | number) => new Intl.NumberFormat(mentorLocale(), { maximumFractionDigits: 0 }).format(Number(value))
    return <View testID="mentor-nutrition-result" style={flowStyles.fill}>
        <MentorFlowHeader onBack={onBack} onClose={onClose} />
        <MentorFlowBody>
            <Text accessibilityRole="header" style={[flowStyles.title, { color: colors.text }]}>{mt("Ваш ориентир питания")}</Text>
            {nutrition ? <>
                <View style={[styles.calorieCard, { backgroundColor: colors.mint }]}>
                    <View style={[styles.foodIcon, { backgroundColor: colors.surface }]}><MentorQuestionIcon name="food" size={29} color={colors.green} /></View>
                    <Text adjustsFontSizeToFit minimumFontScale={0.65} numberOfLines={1} style={[styles.calories, { color: colors.green }]}>{number(nutrition.kcal)}</Text>
                    <Text style={[styles.calorieUnit, { color: colors.green }]}>{mt("ккал в день")}</Text>
                </View>
                <View style={styles.macros}>
                    {([[mt("Белки"), nutrition.protein], [mt("Жиры"), nutrition.fat], [mt("Углеводы"), nutrition.carbs]] as const).map(([name, value], index) => <View key={name} style={[styles.macro, index > 0 && { borderLeftWidth: 1, borderLeftColor: colors.border }]}>
                        <Text numberOfLines={1} adjustsFontSizeToFit style={[styles.macroLabel, { color: colors.muted }]}>{name}</Text>
                        <Text numberOfLines={1} adjustsFontSizeToFit style={[styles.macroValue, { color: colors.text }]}>{number(value)}<Text style={styles.grams}> {mt("г")}</Text></Text>
                        <View style={[styles.macroLine, { backgroundColor: colors.greenBright }]} />
                    </View>)}
                </View>
                <Text style={[styles.explanation, { color: colors.muted }]}>{mt("Начнём с этого ориентира и посмотрим на самочувствие и динамику.")}</Text>
            </> : <View style={[styles.unavailable, { backgroundColor: colors.soft }]}>
                <MentorQuestionIcon name="food" size={36} color={colors.green} />
                <Text style={[styles.explanation, { color: colors.text }]}>{mt("Для ваших параметров нужен индивидуальный ориентир питания.")}</Text>
            </View>}
            <View style={styles.invitation}>
                <Text style={[styles.invitationTitle, { color: colors.text }]}>{mt("Сделаем наставника ещё точнее?")}</Text>
                <Text style={[styles.explanation, { color: colors.muted }]}>{mt("Добавьте привычки, предпочтения и тренировки.")}</Text>
            </View>
        </MentorFlowBody>
        <View style={flowStyles.footer}>
            <MentorFlowButton label={mt("Продолжить заполнение")} onPress={onContinue} />
            <MentorFlowButton label={mt("Нет, пока достаточно")} onPress={onDecline} secondary />
        </View>
    </View>
}

const styles = StyleSheet.create({
    calorieCard: { borderRadius: 28, alignItems: "center", paddingVertical: 24, paddingHorizontal: 18, gap: 6 },
    foodIcon: { width: 52, height: 52, borderRadius: 18, alignItems: "center", justifyContent: "center", marginBottom: 6 },
    calories: { fontSize: 62, lineHeight: 72, fontWeight: "700", letterSpacing: -2.5 }, calorieUnit: { fontSize: 17, fontWeight: "500" },
    macros: { flexDirection: "row", paddingVertical: 5 }, macro: { flex: 1, minWidth: 0, alignItems: "center", gap: 10 },
    macroLabel: { fontSize: 14, fontWeight: "500" }, macroValue: { fontSize: 29, fontWeight: "700", letterSpacing: -0.7 }, grams: { fontSize: 17, fontWeight: "500" }, macroLine: { width: 34, height: 3, borderRadius: 3 },
    explanation: { fontSize: 16, lineHeight: 24 }, invitation: { gap: 8, marginTop: 6 }, invitationTitle: { fontSize: 23, lineHeight: 29, fontWeight: "600", letterSpacing: -0.4 },
    unavailable: { borderRadius: 24, padding: 24, gap: 20 },
})
