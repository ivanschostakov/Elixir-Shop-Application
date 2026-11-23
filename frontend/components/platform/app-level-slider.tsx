import { useRef } from "react"
import { Platform, StyleSheet, View } from "react-native"
import Slider from "@react-native-community/slider"

type Props = {
    label: string
    value: number | null
    minimum?: number
    maximum: number
    onChange: (value: number) => void
    valueText: string
    disabled?: boolean
    color: string
    trackColor: string
    testID?: string
}

/** Native dragging on both phones, with no answer saved until the user touches the control. */
export function AppLevelSlider({ label, value, minimum = 1, maximum, onChange, valueText, disabled = false, color, trackColor, testID }: Props) {
    const last = useRef(value)
    const dragging = useRef(false)
    const nativeValue = useRef(value ?? Math.round((minimum + maximum) / 2))
    last.current = value
    if (!dragging.current) nativeValue.current = value ?? Math.round((minimum + maximum) / 2)
    const select = (raw: number) => {
        if (disabled || !Number.isFinite(raw)) return
        const next = Math.max(minimum, Math.min(maximum, Math.round(raw)))
        if (next !== last.current) { last.current = next; onChange(next) }
    }
    return <View style={styles.container}>
        <Slider testID={testID} accessibilityRole="adjustable" accessibilityState={{ disabled }} accessibilityLabel={label} accessibilityValue={{ min: minimum, max: maximum, ...(value == null ? {} : { now: value }), text: valueText }}
            minimumValue={minimum} maximumValue={maximum} step={1} value={nativeValue.current} disabled={disabled}
            minimumTrackTintColor={color} maximumTrackTintColor={trackColor} thumbTintColor={Platform.OS === "android" ? color : undefined}
            onSlidingStart={raw => { if (!disabled) dragging.current = true; select(raw) }} onValueChange={select}
            onSlidingComplete={raw => { dragging.current = false; if (Number.isFinite(raw)) nativeValue.current = raw; select(raw) }} tapToSeek style={styles.slider} />
    </View>
}

const styles = StyleSheet.create({ container: { minHeight: 48, justifyContent: "center" }, slider: { width: "100%", height: 44 } })
