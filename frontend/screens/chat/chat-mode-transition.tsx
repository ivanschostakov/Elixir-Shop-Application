import { type ReactNode, useEffect, useRef, useState } from "react"
import { AccessibilityInfo, Animated, StyleSheet, View } from "react-native"

import { motion } from "@/theme/motion"
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

/** The shell and wallpaper stay still; only retained screen content crossfades. */
export function ChatModeTransition({ children }: { children: ReactNode; mode: ChatMode }) {
    return <View testID="chat-mode-transition" style={styles.container}>{children}</View>
}

export function ChatModePane({ children, active, mode }: { children: ReactNode; active: boolean; mode: ChatMode }) {
    const reducedMotion = useChatReducedMotion()
    const opacity = useRef(new Animated.Value(active ? 1 : 0)).current

    useEffect(() => {
        opacity.stopAnimation()
        if (reducedMotion) {
            opacity.setValue(active ? 1 : 0)
            return
        }
        const animation = Animated.timing(opacity, { toValue: active ? 1 : 0, duration: motion.duration.standard, easing: motion.easing.standard, useNativeDriver: true })
        animation.start()
        return () => animation.stop()
    }, [active, opacity, reducedMotion])

    return <Animated.View testID={`chat-mode-pane-${mode}`} pointerEvents={active ? "auto" : "none"} accessibilityElementsHidden={!active} importantForAccessibility={active ? "auto" : "no-hide-descendants"} aria-hidden={!active} style={[styles.pane, { opacity, zIndex: active ? 2 : 1 }]}>{children}</Animated.View>
}

const styles = StyleSheet.create({
    container: { flex: 1, minHeight: 0, overflow: "hidden" },
    pane: { ...StyleSheet.absoluteFillObject },
})
