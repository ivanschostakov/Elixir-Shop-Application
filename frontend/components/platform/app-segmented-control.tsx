import { useEffect, useRef, useState } from "react"
import { Animated, Pressable, Text, View, type StyleProp, type TextStyle, type ViewStyle } from "react-native"
import { NativeChatModeControl } from "@/components/platform/native-controls"
import { useReducedMotion } from "@/hooks/use-reduced-motion"

export type SegmentOption<T extends string> = { value: T; label: string; accessibilityLabel?: string; badge?: number }
export type SegmentStyles = {
    modeSwitcher?: StyleProp<ViewStyle>; modeIndicator?: StyleProp<ViewStyle>; modeButton?: StyleProp<ViewStyle>
    modeText?: StyleProp<TextStyle>; modeTextActive?: StyleProp<TextStyle>; modeBadge?: StyleProp<ViewStyle>; modeBadgeText?: StyleProp<TextStyle>
    solidModeSwitcher?: StyleProp<ViewStyle>; solidModeSelection?: StyleProp<ViewStyle>; solidModeText?: StyleProp<TextStyle>; nativeControl?: StyleProp<ViewStyle>
}
type Props<T extends string> = {
    options: readonly SegmentOption<T>[]; value: T; onChange: (value: T) => void; styles: SegmentStyles
    nativeDark?: boolean; preferNative?: boolean; solid?: boolean; disabled?: boolean; label?: string; radio?: boolean
    inset?: number; animation?: "spring" | "timing"; widthShares?: (width: number) => number[]; compactLabels?: boolean
}
export function AppSegmentedControl<T extends string>({ options, value, onChange, styles, nativeDark, preferNative = true, solid = false, disabled = false, label, radio = false, inset = 3, animation = "spring", widthShares, compactLabels }: Props<T>) {
    const index = Math.max(0, options.findIndex(option => option.value === value))
    const native = preferNative && !solid && nativeDark !== undefined && NativeChatModeControl !== null
    const reduced = useReducedMotion(), progress = useRef(new Animated.Value(index)).current
    const [width, setWidth] = useState(0)
    const available = Math.max(0, width - inset * 2)
    const shares = widthShares?.(width) ?? options.map(() => 1 / options.length)
    useEffect(() => {
        if (solid || native) return
        progress.stopAnimation()
        if (reduced) { progress.setValue(index); return }
        const transition = animation === "timing" ? Animated.timing(progress, { toValue: index, duration: 180, useNativeDriver: false }) : Animated.spring(progress, { toValue: index, damping: 20, stiffness: 220, mass: 0.7, useNativeDriver: false })
        transition.start()
        return () => transition.stop()
    }, [animation, index, native, progress, reduced, solid])
    const badge = (count = 0) => count > 99 ? "99+" : count > 0 ? String(count) : ""
    if (native && NativeChatModeControl) return <NativeChatModeControl dark={nativeDark!} labels={options.map(option => option.label)} badges={options.map(option => badge(option.badge))} selectedIndex={index}
        pointerEvents={disabled ? "none" : "auto"} onSelect={({ nativeEvent }) => { const option = options[nativeEvent.index]; if (!disabled && option) onChange(option.value) }} style={[{ flex: 1, minWidth: 0, height: 44 }, styles.nativeControl]} />
    const inputRange = options.map((_, i) => i)
    const indicator = options.length > 1 ? {
        width: progress.interpolate({ inputRange, outputRange: shares.map(share => available * share) }),
        transform: [{ translateX: progress.interpolate({ inputRange, outputRange: shares.map((_, i) => available * shares.slice(0, i).reduce((sum, share) => sum + share, 0)) }) }],
    } : { width: available }
    return <View accessibilityRole={radio ? "radiogroup" : "tablist"} accessibilityLabel={label} onLayout={event => setWidth(event.nativeEvent.layout.width)} style={[styles.modeSwitcher, solid && styles.solidModeSwitcher]}>
        {!solid && width > 0 ? <Animated.View pointerEvents="none" style={[styles.modeIndicator, indicator]} /> : null}
        {options.map((option, i) => <Pressable key={option.value} accessibilityRole={radio ? "radio" : "tab"} accessibilityLabel={option.accessibilityLabel ?? option.label}
            accessibilityState={radio ? { checked: value === option.value, disabled } : { selected: value === option.value, disabled }} disabled={disabled} onPress={() => onChange(option.value)}
            style={[styles.modeButton, { flex: shares[i] }, solid && value === option.value && styles.solidModeSelection]}>
            <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8} style={[styles.modeText, compactLabels && i > 0 && width < 300 && { fontSize: 10.5 }, value === option.value && styles.modeTextActive, solid && styles.solidModeText]}>{option.label}</Text>
            {option.badge && option.badge > 0 ? <View style={styles.modeBadge}><Text style={styles.modeBadgeText}>{badge(option.badge)}</Text></View> : null}
        </Pressable>)}
    </View>
}
