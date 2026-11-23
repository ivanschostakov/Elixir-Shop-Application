import { Pressable, StyleSheet } from "react-native"
import { useLanguage } from "@/providers/language-provider"
import { MentorIcon, useMentorPalette } from "@/screens/chat/mentor-ui"

export function MentorModeToggle({ shown, onToggle, disabled = false }: { shown: boolean; onToggle: () => void; disabled?: boolean }) {
    const { t } = useLanguage()
    const colors = useMentorPalette()
    const label = t(shown ? "chat.hideMentor" : "chat.showMentor")
    return <Pressable
        testID="mentor-mode-shortcut"
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityState={{ expanded: shown, disabled }}
        disabled={disabled}
        onPress={onToggle}
        style={({ pressed }) => [styles.button, { backgroundColor: shown ? colors.mint : colors.surface, opacity: disabled ? 0.45 : pressed ? 0.7 : 1 }]}
    >
        <MentorIcon name={shown ? "chat" : "leaf"} size={28} color={colors.blue} />
    </Pressable>
}

const styles = StyleSheet.create({
    button: { flexShrink: 0, width: 48, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center" },
})
