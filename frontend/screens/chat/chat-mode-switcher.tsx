import { useEffect, useRef, useState } from "react"
import { Animated, type LayoutChangeEvent, Pressable, StyleSheet, Text, View } from "react-native"

import { useLanguage } from "@/providers/language-provider"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { createCommunityChatStyles } from "@/screens/chat/community-chat-screen.styles"
import { useChatReducedMotion } from "@/screens/chat/chat-mode-transition"

export type ChatMode = "ai" | "community" | "support"

export function ChatModeSwitcher({
    mode,
    mentorStyle = false,
    onChange,
    supportUnreadCount = 0,
    unreadCount,
}: {
    mode: ChatMode
    mentorStyle?: boolean
    onChange: (mode: ChatMode) => void
    supportUnreadCount?: number
    unreadCount: number
}) {
    const themeStyles = useThemeStyles(createCommunityChatStyles)
    const styles = mentorStyle ? mentorSwitcherStyles : themeStyles
    const { t } = useLanguage()
    const modeIndex = mode === "community" ? 1 : mode === "support" ? 2 : 0
    const reducedMotion = useChatReducedMotion()
    const progress = useRef(new Animated.Value(modeIndex)).current
    const [switcherWidth, setSwitcherWidth] = useState(0)
    const availableWidth = Math.max(0, switcherWidth - (mentorStyle ? 8 : 6))
    const shares = mentorStyle ? (switcherWidth < 300 ? [0.20, 0.48, 0.32] : [0.30, 0.40, 0.30]) : [1 / 3, 1 / 3, 1 / 3]
    const indicatorWidth = progress.interpolate({ inputRange: [0, 1, 2], outputRange: shares.map((share) => availableWidth * share) })
    const indicatorPosition = progress.interpolate({ inputRange: [0, 1, 2], outputRange: [0, availableWidth * shares[0], availableWidth * (shares[0] + shares[1])] })

    const handleLayout = (event: LayoutChangeEvent) => {
        const nextWidth = event.nativeEvent.layout.width
        setSwitcherWidth((currentWidth) => currentWidth === nextWidth ? currentWidth : nextWidth)
    }

    useEffect(() => {
        progress.stopAnimation()
        if (reducedMotion) {
            progress.setValue(modeIndex)
            return
        }
        const animation = Animated.spring(progress, { toValue: modeIndex, damping: 20, stiffness: 220, mass: 0.7, useNativeDriver: false })
        animation.start()
        return () => animation.stop()
    }, [modeIndex, progress, reducedMotion])

    return (
        <View accessibilityRole="tablist" onLayout={handleLayout} style={[themeStyles.modeSwitcher, mentorStyle ? mentorSwitcherStyles.modeSwitcher : null]}>
            {availableWidth > 0 ? <Animated.View pointerEvents="none" style={[styles.modeIndicator, { width: indicatorWidth, transform: [{ translateX: indicatorPosition }] }]} /> : null}
            <Pressable accessibilityRole="tab" accessibilityState={{ selected: mode === "ai" }} onPress={() => onChange("ai")} style={[styles.modeButton, { flex: shares[0] }]}>
                <Text style={[styles.modeText, mode === "ai" ? styles.modeTextActive : null]}>{t("chat.modeAi")}</Text>
            </Pressable>
            <Pressable accessibilityRole="tab" accessibilityState={{ selected: mode === "community" }} onPress={() => onChange("community")} style={[styles.modeButton, { flex: shares[1] }]}>
                <Text adjustsFontSizeToFit minimumFontScale={0.8} numberOfLines={1} style={[styles.modeText, mentorStyle && switcherWidth < 300 ? { fontSize: 10.5 } : null, mode === "community" ? styles.modeTextActive : null]}>{t("chat.modeGroup")}</Text>
                {unreadCount > 0 ? <View style={styles.modeBadge}><Text style={styles.modeBadgeText}>{unreadCount > 99 ? "99+" : unreadCount}</Text></View> : null}
            </Pressable>
            <Pressable accessibilityRole="tab" accessibilityState={{ selected: mode === "support" }} onPress={() => onChange("support")} style={[styles.modeButton, { flex: shares[2] }]}>
                <Text adjustsFontSizeToFit minimumFontScale={0.8} numberOfLines={1} style={[styles.modeText, mentorStyle && switcherWidth < 300 ? { fontSize: 10.5 } : null, mode === "support" ? styles.modeTextActive : null]}>{t("chat.modeSupport")}</Text>
                {supportUnreadCount > 0 ? <View style={styles.modeBadge}><Text style={styles.modeBadgeText}>{supportUnreadCount > 99 ? "99+" : supportUnreadCount}</Text></View> : null}
            </Pressable>
        </View>
    )
}

const mentorSwitcherStyles = StyleSheet.create({
    modeSwitcher: { flex: 1, minWidth: 0, height: 42, padding: 3, borderRadius: 23, flexDirection: "row", overflow: "hidden", shadowOpacity: 0, elevation: 0 },
    modeIndicator: { position: "absolute", left: 3, top: 3, height: 34, borderRadius: 19, backgroundColor: "#078AFF" },
    modeButton: { flex: 1, minWidth: 0, height: 34, paddingHorizontal: 4, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 4, zIndex: 1 },
    modeText: { flexShrink: 1, color: "#616B77", fontSize: 12, lineHeight: 16, fontWeight: "700", textAlign: "center" },
    modeTextActive: { color: "#FFFFFF" },
    modeBadge: { minWidth: 18, height: 18, paddingHorizontal: 4, borderRadius: 9, backgroundColor: "#CB1745", alignItems: "center", justifyContent: "center" },
    modeBadgeText: { color: "#FFFFFF", fontSize: 10, lineHeight: 12, fontWeight: "600" },
})
