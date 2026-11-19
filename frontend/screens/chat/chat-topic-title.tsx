import { StyleSheet, Text, View, type ViewProps } from "react-native"
import { useTheme } from "@/providers/theme-provider"
import { NativeChatTitleMaterial } from "@/screens/chat/native-chat-controls"

export function ChatTopicTitle({ title, style }: { title: string; style?: ViewProps["style"] }) {
    const { isDark, palette } = useTheme()
    return <View style={[styles.pill, !NativeChatTitleMaterial && { backgroundColor: palette.surfaceOverlaySoft }, style]}>
        {NativeChatTitleMaterial ? <NativeChatTitleMaterial dark={isDark} pointerEvents="none" style={StyleSheet.absoluteFill} /> : null}
        <Text numberOfLines={1} style={[styles.title, { color: palette.text }]}>{title}</Text>
    </View>
}

const styles = StyleSheet.create({
    pill: { flex: 1, minWidth: 0, height: 44, borderRadius: 22, justifyContent: "center", paddingHorizontal: 16 },
    title: { fontSize: 16, fontWeight: "600", textAlign: "center" },
})
