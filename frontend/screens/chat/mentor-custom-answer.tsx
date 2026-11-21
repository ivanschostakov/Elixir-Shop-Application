import { Keyboard, Pressable, StyleSheet, Text, TextInput, View } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { MentorQuestionIcon } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"

export function MentorCustomAnswer({ label, placeholder, value, onChange, onCancel, disabled, maxLength = 2000 }: {
    label: string; placeholder: string; value: string; onChange: (value: string) => void; onCancel: () => void; disabled: boolean; maxLength?: number
}) {
    const colors = useMentorPalette()
    return <View style={[styles.card, { backgroundColor: colors.soft, borderColor: colors.border }]}>
        <View style={styles.header}>
            <MentorQuestionIcon name="custom" size={20} color={colors.green} />
            <Text style={[styles.label, { color: colors.green }]}>{label}</Text>
            <Pressable accessibilityRole="button" accessibilityLabel={mt("Вернуться к вариантам")} disabled={disabled} accessibilityState={{ disabled }}
                onPress={() => { Keyboard.dismiss(); onCancel() }} style={({ pressed }) => [styles.close, { opacity: pressed ? 0.6 : 1 }]}>
                <MentorQuestionIcon name="close" size={22} color={colors.muted} />
            </Pressable>
        </View>
        <TextInput accessibilityLabel={label} placeholder={placeholder} placeholderTextColor={colors.muted} value={value} onChangeText={onChange}
            autoFocus={!disabled} multiline textAlignVertical="top" maxLength={maxLength} editable={!disabled} selectionColor={colors.greenBright}
            style={[styles.input, { color: colors.text }]} />
    </View>
}

const styles = StyleSheet.create({
    card: { borderRadius: 22, borderWidth: 1, paddingHorizontal: 18, paddingTop: 8, paddingBottom: 18 },
    header: { flexDirection: "row", alignItems: "center", gap: 9 }, label: { flex: 1, fontSize: 15, lineHeight: 22, fontWeight: "700" },
    close: { width: 44, height: 44, marginRight: -9, alignItems: "center", justifyContent: "center" },
    input: { fontWeight: "500", minHeight: 158, paddingTop: 8, paddingBottom: 0, paddingHorizontal: 0, fontSize: 18, lineHeight: 28 },
})
