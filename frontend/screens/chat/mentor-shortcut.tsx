import { Pressable, StyleSheet, View } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { NativeChatAction, NativeChatTitleMaterial, nativeChatMentorActionAvailable } from "@/screens/chat/native-chat-controls"
import { MentorIcon } from "@/screens/chat/mentor-ui"

export function MentorShortcut({ onPress, disabled = false }: { onPress: () => void; disabled?: boolean }) {
    useLanguage()
    const { isDark, palette } = useTheme()
    const label = mt("Открыть наставника")
    if (NativeChatAction && nativeChatMentorActionAvailable) return <NativeChatAction testID="mentor-open-shortcut" action="mentor" dark={isDark} label={label} disabled={disabled} onAction={onPress} style={styles.button} />
    return <Pressable testID="mentor-open-shortcut" accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
        style={({ pressed }) => [styles.button, { opacity: disabled ? 0.45 : pressed ? 0.7 : 1 }]}>
        {NativeChatTitleMaterial ? <NativeChatTitleMaterial dark={isDark} pointerEvents="none" style={StyleSheet.absoluteFill} /> : <View pointerEvents="none" style={[StyleSheet.absoluteFill, styles.fallback, { backgroundColor: palette.surface }]} />}
        <MentorIcon name="leaf" size={25} />
    </Pressable>
}

const styles = StyleSheet.create({
    button: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center", flexShrink: 0 },
    fallback: { borderRadius: 22 },
})
