import { Pressable, StyleSheet, Text, View } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { NativeChatAction, NativeChatTitleMaterial, nativeChatMentorGreetingAvailable } from "@/screens/chat/native-chat-controls"
import { MentorIcon } from "@/screens/chat/mentor-ui"
import type { ProfileData } from "@/services/api/companion"

export const MENTOR_SHORTCUT_HEIGHT = 58

export function MentorShortcut({ onPress, disabled = false, goal }: { onPress: () => void; disabled?: boolean; goal?: ProfileData["goal"] }) {
    useLanguage()
    const { isDark, palette } = useTheme()
    const title = goal === "weight_loss" ? mt("Ваш наставник по похудению\nНажмите, чтобы открыть") : goal === "weight_gain" ? mt("Ваш наставник по набору веса\nНажмите, чтобы открыть") : mt("Ваш наставник по питанию\nНажмите, чтобы открыть")
    const accessibilityLabel = title.replace("\n", ". ")
    if (NativeChatAction && nativeChatMentorGreetingAvailable) return <NativeChatAction testID="mentor-open-shortcut" action="mentor" title={title} dark={isDark} label={accessibilityLabel} disabled={disabled} onAction={onPress} style={styles.button} />
    return <Pressable testID="mentor-open-shortcut" accessibilityRole="button" accessibilityLabel={accessibilityLabel} accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
        style={({ pressed }) => [styles.button, { opacity: disabled ? 0.45 : pressed ? 0.7 : 1 }]}>
        {NativeChatTitleMaterial ? <NativeChatTitleMaterial dark={isDark} pointerEvents="none" style={StyleSheet.absoluteFill} /> : <View pointerEvents="none" style={[StyleSheet.absoluteFill, styles.fallback, { backgroundColor: palette.surface }]} />}
        <MentorIcon name="leaf" size={25} />
        <Text numberOfLines={2} style={[styles.label, { color: palette.text }]}>{title}</Text>
    </Pressable>
}

const styles = StyleSheet.create({
    button: { width: "100%", height: MENTOR_SHORTCUT_HEIGHT, borderRadius: 29, flexDirection: "row", gap: 11, alignItems: "center", paddingHorizontal: 16 },
    label: { flex: 1, fontSize: 14, lineHeight: 19, fontWeight: "500" },
    fallback: { borderRadius: 29 },
})
