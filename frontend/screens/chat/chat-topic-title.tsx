import { StyleSheet, Text, View, type ViewProps } from "react-native"
import { useTheme } from "@/providers/theme-provider"
import { AppSurface } from "@/components/platform/app-surface"
import { CommunityNotificationButton, type TopicNotificationAction } from "@/screens/chat/community-notifications"

export type ChatTopicNavigation = { title: string; onBack: () => void; notifications?: TopicNotificationAction }

export function ChatTopicTitle({ title, style, notifications }: { title: string; style?: ViewProps["style"]; notifications?: TopicNotificationAction }) {
    const { isDark, palette } = useTheme()
    return <View style={[styles.pill, style]}>
        <AppSurface dark={isDark} fallbackColor={palette.surfaceOverlaySoft} pointerEvents="none" style={StyleSheet.absoluteFill} />
        <Text accessibilityRole="header" numberOfLines={1} style={[styles.title, { color: palette.text }, notifications && { paddingHorizontal: 28 }]}>{title}</Text>
        {notifications ? <View style={styles.action}><CommunityNotificationButton {...notifications} /></View> : null}
    </View>
}

const styles = StyleSheet.create({
    pill: { flex: 1, minWidth: 0, height: 44, borderRadius: 22, justifyContent: "center", paddingHorizontal: 16 },
    title: { fontSize: 16, fontWeight: "600", textAlign: "center" },
    action: { position: "absolute", right: 2, top: 0 },
})
