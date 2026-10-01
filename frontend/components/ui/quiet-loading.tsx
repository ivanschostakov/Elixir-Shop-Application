import { type ReactNode, useEffect, useRef, useState } from "react"
import { Animated, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native"
import { useTheme } from "@/providers/theme-provider"
import { useLanguage } from "@/providers/language-provider"
import { motion } from "@/theme/motion"
import { useChatReducedMotion } from "@/screens/chat/chat-mode-transition"

export function ContentReveal({ ready, children, style }: { ready: boolean; children: ReactNode; style?: StyleProp<ViewStyle> }) {
    const reducedMotion = useChatReducedMotion()
    const opacity = useRef(new Animated.Value(ready ? 1 : 0)).current
    useEffect(() => {
        opacity.stopAnimation()
        if (reducedMotion) { opacity.setValue(ready ? 1 : 0); return }
        const animation = Animated.timing(opacity, { toValue: ready ? 1 : 0, duration: motion.duration.enter, easing: motion.easing.enter, useNativeDriver: true })
        animation.start()
        return () => animation.stop()
    }, [ready, reducedMotion, opacity])
    return <Animated.View pointerEvents={ready ? "auto" : "none"} accessibilityElementsHidden={!ready} importantForAccessibility={ready ? "auto" : "no-hide-descendants"} style={[style, { opacity }]}>{children}</Animated.View>
}

/** Fast requests show nothing; slow ones reveal still, softly fading placeholders. */
export function QuietLoading({ loading, kind = "chat" }: { loading: boolean; kind?: "chat" | "content" }) {
    const { palette } = useTheme()
    const { t } = useLanguage()
    const reducedMotion = useChatReducedMotion()
    const [visible, setVisible] = useState(false)
    const opacity = useRef(new Animated.Value(0)).current
    useEffect(() => {
        if (!loading) {
            setVisible(false)
            opacity.stopAnimation()
            opacity.setValue(0)
            return
        }
        const timer = setTimeout(() => setVisible(true), 220)
        return () => clearTimeout(timer)
    }, [loading, opacity])
    useEffect(() => {
        if (!visible) return
        if (reducedMotion) { opacity.setValue(1); return }
        const animation = Animated.timing(opacity, { toValue: 1, duration: motion.duration.enter, easing: motion.easing.enter, useNativeDriver: true })
        animation.start()
        return () => animation.stop()
    }, [visible, opacity, reducedMotion])
    if (!loading || !visible) return null
    return <Animated.View testID="quiet-loading" accessibilityRole="progressbar" accessibilityLabel={t("common.loading")} style={[styles.container, { opacity }]}>
        {[0, 1, 2].map(index => <View key={index} style={[styles.block, kind === "chat" ? { width: index === 1 ? "56%" : "76%", alignSelf: index === 1 ? "flex-end" : "flex-start" } : { width: "100%" }, { backgroundColor: palette.surfaceOverlaySoft }]}>
            <View style={[styles.line, { width: "72%", backgroundColor: palette.borderSoft }]} />
            <View style={[styles.line, { width: "46%", backgroundColor: palette.borderSoft }]} />
        </View>)}
    </Animated.View>
}
const styles = StyleSheet.create({
    container: { padding: 16, gap: 12, width: "100%", maxWidth: 700, alignSelf: "center" },
    block: { minHeight: 78, padding: 16, gap: 12, borderRadius: 20 },
    line: { height: 10, borderRadius: 5, opacity: 0.45 },
})
