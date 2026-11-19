import { Pressable, StyleSheet, Text, View } from "react-native"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { MentorFlowButton } from "@/screens/chat/mentor-onboarding-layout"

export function MentorDevelopmentNotice({ onChat, onContinue }: { onChat: () => void; onContinue?: () => void }) {
    const { t } = useLanguage()
    const { palette } = useTheme()
    return <View testID="mentor-development-notice" style={styles.container}>
        <Text style={[styles.title, { color: palette.text }]}>{t("chat.mentorTitle")}</Text>
        <Text style={[styles.message, { color: palette.stateText }]}>{t("chat.mentorInDevelopment")}</Text>
        {onContinue ? <View style={styles.continue}><MentorFlowButton label={mt("Продолжить заполнение")} onPress={onContinue} /></View> : null}
        <Pressable accessibilityRole="button" onPress={onChat} style={[styles.button, { backgroundColor: palette.primary }]}>
            <Text style={[styles.buttonText, { color: palette.onPrimary }]}>{t("chat.backToAiChat")}</Text>
        </Pressable>
    </View>
}

const styles = StyleSheet.create({
    container: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 24, gap: 12 },
    title: { fontSize: 24, fontWeight: "700", textAlign: "center" },
    message: { fontSize: 17, textAlign: "center" },
    continue: { width: "100%", maxWidth: 360, marginTop: 20 },
    button: { minHeight: 44, paddingHorizontal: 20, borderRadius: 22, alignItems: "center", justifyContent: "center", marginTop: 8 },
    buttonText: { fontSize: 15, fontWeight: "600" },
})
