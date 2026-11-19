import { Pressable, StyleSheet, Text, View } from "react-native"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"

export function MentorDevelopmentNotice({ onChat }: { onChat: () => void }) {
    const { t } = useLanguage()
    const { palette } = useTheme()
    return <View testID="mentor-development-notice" style={styles.container}>
        <Text style={[styles.title, { color: palette.text }]}>{t("chat.mentorTitle")}</Text>
        <Text style={[styles.message, { color: palette.stateText }]}>{t("chat.mentorInDevelopment")}</Text>
        <Pressable accessibilityRole="button" onPress={onChat} style={[styles.button, { backgroundColor: palette.primary }]}>
            <Text style={[styles.buttonText, { color: palette.onPrimary }]}>{t("chat.backToAiChat")}</Text>
        </Pressable>
    </View>
}

const styles = StyleSheet.create({
    container: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 24, gap: 12 },
    title: { fontSize: 24, fontWeight: "700", textAlign: "center" },
    message: { fontSize: 17, textAlign: "center" },
    button: { minHeight: 44, paddingHorizontal: 20, borderRadius: 22, alignItems: "center", justifyContent: "center", marginTop: 8 },
    buttonText: { fontSize: 15, fontWeight: "600" },
})
