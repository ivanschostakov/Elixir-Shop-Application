import { useEffect, useRef, useState } from "react"
import { Animated, type LayoutChangeEvent, Pressable, Text, View } from "react-native"

import { useLanguage } from "@/providers/language-provider"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { createCommunityChatStyles } from "@/screens/chat/community-chat-screen.styles"

export type ChatMode = "ai" | "community"

export function ChatModeSwitcher({ mode, onChange, unreadCount }: { mode: ChatMode; onChange: (mode: ChatMode) => void; unreadCount: number }) {
    const styles = useThemeStyles(createCommunityChatStyles)
    const { t } = useLanguage()
    const progress = useRef(new Animated.Value(mode === "community" ? 1 : 0)).current
    const [switcherWidth, setSwitcherWidth] = useState(0)
    const indicatorWidth = Math.max(0, (switcherWidth - 6) / 2)

    const handleLayout = (event: LayoutChangeEvent) => {
        const nextWidth = event.nativeEvent.layout.width
        setSwitcherWidth((currentWidth) => currentWidth === nextWidth ? currentWidth : nextWidth)
    }

    useEffect(() => {
        Animated.spring(progress, { toValue: mode === "community" ? 1 : 0, damping: 20, stiffness: 220, mass: 0.7, useNativeDriver: true }).start()
    }, [mode, progress])

    return (
        <View accessibilityRole="tablist" onLayout={handleLayout} style={styles.modeSwitcher}>
            {indicatorWidth > 0 ? <Animated.View style={[styles.modeIndicator, { width: indicatorWidth, transform: [{ translateX: progress.interpolate({ inputRange: [0, 1], outputRange: [0, indicatorWidth] }) }] }]} /> : null}
            <Pressable accessibilityRole="tab" accessibilityState={{ selected: mode === "ai" }} onPress={() => onChange("ai")} style={styles.modeButton}>
                <Text style={[styles.modeText, mode === "ai" ? styles.modeTextActive : null]}>{t("chat.modeAi")}</Text>
            </Pressable>
            <Pressable accessibilityRole="tab" accessibilityState={{ selected: mode === "community" }} onPress={() => onChange("community")} style={styles.modeButton}>
                <Text numberOfLines={1} style={[styles.modeText, mode === "community" ? styles.modeTextActive : null]}>{t("chat.modeGroup")}</Text>
                {unreadCount > 0 ? <View style={styles.modeBadge}><Text style={styles.modeBadgeText}>{unreadCount > 99 ? "99+" : unreadCount}</Text></View> : null}
            </Pressable>
        </View>
    )
}
