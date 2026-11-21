import { useEffect, useState } from "react"
import { Pressable, StyleSheet, Text, View } from "react-native"
import Animated, { Easing, ReduceMotion, useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { mainMeals, mealLabel } from "@/screens/chat/mentor-meals-data"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import type { MealType } from "@/services/api/companion"

const options = [...mainMeals, "extra"] as const
export function MentorMealSelector({ value, onChange, disabled }: { value: MealType; onChange: (value: MealType) => void; disabled: boolean }) {
    const colors = useMentorPalette(), [width, setWidth] = useState(0)
    const index = options.indexOf(value), position = useSharedValue(index)
    useEffect(() => { position.value = withTiming(index, { duration: 180, easing: Easing.bezier(0.2, 0, 0, 1), reduceMotion: ReduceMotion.System }) }, [index, position])
    const cell = Math.max(0, width - 8) / 4
    const indicator = useAnimatedStyle(() => ({ transform: [{ translateX: position.value * cell }] }))
    return <View accessibilityRole="radiogroup" accessibilityLabel={mt("Выбрать приём пищи")} onLayout={event => setWidth(event.nativeEvent.layout.width)} style={[styles.selector, { backgroundColor: colors.soft }]}>
        {width > 0 ? <Animated.View pointerEvents="none" style={[styles.indicator, { width: cell, backgroundColor: colors.surface }, indicator]} /> : null}
        {options.map(type => <Pressable key={type} accessibilityRole="radio" accessibilityLabel={mealLabel(type)} accessibilityState={{ checked: type === value, disabled }} disabled={disabled} onPress={() => onChange(type)} style={styles.option}><Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8} style={[styles.label, { color: type === value ? colors.green : colors.muted, fontWeight: type === value ? "800" : "600" }]}>{type === "extra" ? mt("Ещё") : mealLabel(type)}</Text></Pressable>)}
    </View>
}

const styles = StyleSheet.create({ selector: { flexDirection: "row", padding: 4, borderRadius: 17 }, option: { flex: 1, minHeight: 42, alignItems: "center", justifyContent: "center", paddingHorizontal: 5 }, label: { fontSize: 14, lineHeight: 20 }, indicator: { position: "absolute", top: 4, bottom: 4, left: 4, borderRadius: 13, shadowColor: "#000000", shadowOpacity: 0.06, shadowRadius: 4, shadowOffset: { width: 0, height: 1 } } })
