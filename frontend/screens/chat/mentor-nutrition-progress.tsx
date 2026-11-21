import { useEffect } from "react"
import { StyleSheet, View } from "react-native"
import Svg, { Circle } from "react-native-svg"
import Animated, { cancelAnimation, Easing, ReduceMotion, useAnimatedProps, useAnimatedStyle, useSharedValue, withDelay, withTiming } from "react-native-reanimated"
import { nutritionFraction } from "@/screens/chat/mentor-home-data"
import { MentorQuestionIcon } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"

const AnimatedCircle = Animated.createAnimatedComponent(Circle)
const radius = 34, circumference = 2 * Math.PI * radius

function useNutritionFill(amount: unknown, target: unknown, delay: number) {
    const progress = useSharedValue(0)
    const fraction = nutritionFraction(amount, target)
    useEffect(() => {
        // Timing and SVG props run on the UI thread, including mid-animation updates.
        progress.value = withDelay(delay, withTiming(fraction, { duration: 900, easing: Easing.bezier(0.2, 0.7, 0.2, 1), reduceMotion: ReduceMotion.System }), ReduceMotion.System)
        return () => cancelAnimation(progress)
    }, [fraction, delay, progress])
    return progress
}

export function MentorCalorieRing({ amount, target, label, size = 80, kind = "food" }: { amount: unknown; target: unknown; label: string; size?: number; kind?: "food" | "water" }) {
    const colors = useMentorPalette()
    const color = kind === "water" ? colors.blue : colors.green
    const progress = useNutritionFill(amount, target, 0)
    const animatedProps = useAnimatedProps(() => ({ strokeDashoffset: circumference * (1 - progress.value), strokeOpacity: progress.value > 0 ? 1 : 0 }))
    return <View accessibilityRole="progressbar" accessibilityLabel={label} accessibilityValue={{ min: 0, max: 100, now: Math.round(nutritionFraction(amount, target) * 100) }} style={[styles.ring, { width: size, height: size }]}>
        <Svg width={size} height={size} viewBox="0 0 80 80" accessible={false}>
            <Circle cx={40} cy={40} r={radius} stroke={kind === "water" ? `${color}35` : colors.border} strokeWidth={7} fill="none" />
            <AnimatedCircle cx={40} cy={40} r={radius} stroke={color} strokeWidth={7} fill="none" strokeLinecap="round" strokeDasharray={`${circumference} ${circumference}`} rotation={-90} origin="40, 40" animatedProps={animatedProps} />
        </Svg>
        <View pointerEvents="none" style={styles.center}><MentorQuestionIcon name={kind} size={kind === "water" ? size * 0.35 : size < 72 ? 21 : 25} color={color} /></View>
    </View>
}

export function MentorMacroProgress({ amount, target, label, index, color }: { amount: unknown; target: unknown; label: string; index: number; color?: string }) {
    const colors = useMentorPalette()
    const progress = useNutritionFill(amount, target, 60 * (index + 1))
    const animatedStyle = useAnimatedStyle(() => ({ width: `${progress.value * 100}%` }))
    return <View accessibilityRole="progressbar" accessibilityLabel={label} accessibilityValue={{ min: 0, max: 100, now: Math.round(nutritionFraction(amount, target) * 100) }} style={[styles.track, { backgroundColor: color ? `${color}25` : colors.border }]}>
        <Animated.View style={[styles.fill, { backgroundColor: color ?? colors.greenBright }, animatedStyle]} />
    </View>
}

const styles = StyleSheet.create({
    ring: { width: 80, height: 80, flexShrink: 0 }, center: { ...StyleSheet.absoluteFillObject, alignItems: "center", justifyContent: "center" },
    track: { height: 7, flex: 1, minWidth: 24, borderRadius: 4, overflow: "hidden" }, fill: { height: "100%", borderRadius: 4 },
})
