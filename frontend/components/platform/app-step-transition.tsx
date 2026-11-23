import { useEffect, type ReactNode } from "react"
import { StyleSheet, View } from "react-native"
import Animated, { Easing, ReduceMotion, cancelAnimation, runOnUI, useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated"

const transition = { duration: 240, easing: Easing.bezier(0.22, 0.7, 0.22, 1), reduceMotion: ReduceMotion.System }

function StepPane({ active, direction, children }: { active: boolean; direction: number; children: ReactNode }) {
    const position = useSharedValue(active ? 0 : 1)
    const selected = useSharedValue(active)
    useEffect(() => {
        runOnUI((shown: boolean, nextDirection: number) => {
            const wasSelected = selected.value
            selected.value = shown
            if (shown) {
                if (Math.abs(position.value) >= 1) position.value = nextDirection
                position.value = withTiming(0, transition)
            } else if (wasSelected) {
                const edge = Math.abs(position.value) > 0.001 ? Math.sign(position.value) : -nextDirection
                position.value = withTiming(edge, transition)
            }
        })(active, direction)
    }, [active, direction, position, selected])
    useEffect(() => () => cancelAnimation(position), [position])
    const style = useAnimatedStyle(() => ({ transform: [{ translateX: `${position.value * 100}%` }] }))
    return <Animated.View pointerEvents={active ? "auto" : "none"} accessibilityElementsHidden={!active} importantForAccessibility={active ? "auto" : "no-hide-descendants"} style={[StyleSheet.absoluteFill, { zIndex: active ? 1 : 0 }, style]}>{children}</Animated.View>
}

/** The two pages share the same timing; interrupted back/next taps retain their current position. */
export function AppStepTransition({ step, direction, count, render }: { step: number; direction: number; count: number; render: (index: number) => ReactNode }) {
    return <View collapsable={false} style={styles.viewport}>
        {Array.from({ length: count }, (_, index) => <StepPane key={index} active={index === step} direction={direction}>{render(index)}</StepPane>)}
    </View>
}

const styles = StyleSheet.create({ viewport: { flex: 1, minHeight: 0, overflow: "hidden" } })
