import { createContext, type ReactNode, useContext, useEffect, useRef, useState } from "react"
import { AccessibilityInfo, Animated, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native"

import type { ChatMode } from "@/screens/chat/chat-mode-switcher"

export function useChatReducedMotion() {
    const [reducedMotion, setReducedMotion] = useState(true)

    useEffect(() => {
        let mounted = true
        void AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
            if (mounted) setReducedMotion(enabled)
        }).catch(() => {
            // Keep transitions still when the accessibility preference is unavailable.
        })
        const subscription = AccessibilityInfo.addEventListener("reduceMotionChanged", setReducedMotion)
        return () => {
            mounted = false
            subscription.remove()
        }
    }, [])

    return reducedMotion
}

const indices = { ai: 0, community: 1, support: 2 }
const SlideContext = createContext<{ progress: Animated.Value; width: number } | null>(null)

/** One native-driven track keeps retained panes moving together, including rapid taps. */
export function ChatModeTransition({ children, style, mode }: { children: ReactNode; mode: ChatMode; style?: StyleProp<ViewStyle> }) {
    const reducedMotion = useChatReducedMotion()
    const progress = useRef(new Animated.Value(indices[mode])).current
    const [width, setWidth] = useState(0)
    useEffect(() => {
        if (reducedMotion || !width) {
            progress.setValue(indices[mode])
            return
        }
        const animation = Animated.spring(progress, { toValue: indices[mode], damping: 32, stiffness: 300, mass: 1, overshootClamping: true, useNativeDriver: true })
        animation.start()
        return () => animation.stop()
    }, [mode, progress, reducedMotion, width])
    return <View testID="chat-mode-transition" onLayout={event => setWidth(event.nativeEvent.layout.width)} style={[styles.container, style]}><SlideContext.Provider value={{ progress, width }}>{children}</SlideContext.Provider></View>
}

export function ChatModePane({ children, active, mode }: { children: ReactNode; active: boolean; mode: ChatMode }) {
    const slide = useContext(SlideContext)
    const transform = slide ? [{ translateX: slide.progress.interpolate({ inputRange: [0, 1, 2], outputRange: [indices[mode] * slide.width, (indices[mode] - 1) * slide.width, (indices[mode] - 2) * slide.width] }) }] : undefined
    return <Animated.View testID={`chat-mode-pane-${mode}`} pointerEvents={active ? "auto" : "none"} accessibilityElementsHidden={!active} importantForAccessibility={active ? "auto" : "no-hide-descendants"} aria-hidden={!active} style={[styles.pane, { transform, opacity: slide?.width || active ? 1 : 0 }]}>{children}</Animated.View>
}

const styles = StyleSheet.create({
    container: { flex: 1, minHeight: 0, overflow: "hidden" },
    pane: { ...StyleSheet.absoluteFillObject },
})
