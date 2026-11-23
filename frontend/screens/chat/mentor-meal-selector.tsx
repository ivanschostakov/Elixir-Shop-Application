import { StyleSheet } from "react-native"
import { AppSegmentedControl } from "@/components/platform/app-segmented-control"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { mainMeals, mealLabel } from "@/screens/chat/mentor-meals-data"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import type { MealType } from "@/services/api/companion"

const options = [...mainMeals, "extra"] as const
export function MentorMealSelector({ value, onChange, disabled }: { value: MealType; onChange: (value: MealType) => void; disabled: boolean }) {
    const colors = useMentorPalette()
    return <AppSegmentedControl value={value} onChange={onChange} disabled={disabled} label={mt("Выбрать приём пищи")} radio preferNative={false} inset={4} animation="timing"
        options={options.map(type => ({ value: type, label: type === "extra" ? mt("Ещё") : mealLabel(type), accessibilityLabel: mealLabel(type) }))}
        styles={{ modeSwitcher: [styles.selector, { backgroundColor: colors.soft }], modeIndicator: [styles.indicator, { backgroundColor: colors.surface }], modeButton: styles.option,
            modeText: [styles.label, { color: colors.muted }], modeTextActive: { color: colors.green, fontWeight: "800" } }} />
}
const styles = StyleSheet.create({ selector: { flexDirection: "row", padding: 4, borderRadius: 17 }, option: { flex: 1, minHeight: 42, alignItems: "center", justifyContent: "center", paddingHorizontal: 5 }, label: { fontSize: 14, lineHeight: 20, fontWeight: "600" }, indicator: { position: "absolute", top: 4, bottom: 4, left: 4, borderRadius: 13, shadowColor: "#000000", shadowOpacity: 0.06, shadowRadius: 4, shadowOffset: { width: 0, height: 1 } } })
