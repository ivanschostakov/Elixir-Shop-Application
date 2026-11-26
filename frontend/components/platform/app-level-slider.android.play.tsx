import { useRef, useState } from "react"
import { StyleSheet, View, type GestureResponderEvent } from "react-native"
import type { AppLevelSliderProps } from "./app-level-slider"

const radius = 10

export function AppLevelSlider({ label, minimum = 1, maximum, value, valueText, disabled = false, onChange, color, trackColor, testID }: AppLevelSliderProps) {
    const [width, setWidth] = useState(0)
    const current = value ?? Math.round((minimum + maximum) / 2)
    const lastTouch = useRef<number | null>(null)
    const trackWidth = Math.max(0, width - 2 * radius)
    const span = maximum - minimum
    const offset = span > 0 ? trackWidth * (current - minimum) / span : 0

    function selectAt(event: GestureResponderEvent) {
        if (disabled || !trackWidth) return
        const fraction = Math.min(1, Math.max(0, (event.nativeEvent.locationX - radius) / trackWidth))
        const next = minimum + Math.round(fraction * span)
        if (lastTouch.current !== next) {
            lastTouch.current = next
            onChange(next)
        }
    }

    return <View testID={testID} accessible accessibilityRole="adjustable" accessibilityLabel={label}
        accessibilityValue={{ min: minimum, max: maximum, now: value ?? undefined, text: valueText }} accessibilityState={{ disabled }}
        accessibilityActions={[{ name: "increment" }, { name: "decrement" }]}
        onAccessibilityAction={({ nativeEvent }) => {
            if (disabled) return
            if (nativeEvent.actionName === "increment") onChange(Math.min(maximum, current + 1))
            if (nativeEvent.actionName === "decrement") onChange(Math.max(minimum, current - 1))
        }}
        onLayout={event => setWidth(event.nativeEvent.layout.width)} style={styles.slider}
        onStartShouldSetResponder={() => !disabled}
        onResponderGrant={event => { lastTouch.current = value; selectAt(event) }}
        onResponderMove={selectAt}>
        <View pointerEvents="none" style={[styles.track, { backgroundColor: trackColor }]}>
            <View style={[styles.fill, { width: offset, backgroundColor: color }]} />
        </View>
        <View pointerEvents="none" style={[styles.thumb, { left: offset, backgroundColor: color }]} />
    </View>
}

const styles = StyleSheet.create({
    slider: { height: 48, justifyContent: "center" },
    track: { marginHorizontal: radius, height: 4, borderRadius: 2 },
    fill: { height: 4, borderRadius: 2 },
    thumb: { position: "absolute", top: 24 - radius, width: 2 * radius, height: 2 * radius, borderRadius: radius },
})
