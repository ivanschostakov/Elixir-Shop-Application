import { Pressable, StyleSheet, Text, View } from "react-native"
import { MentorQuestionIcon, type MentorQuestionIconName } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"

export function MentorChoiceCard({ title, description, icon, selected, onPress, disabled }: { title: string; description?: string; icon?: MentorQuestionIconName; selected: boolean; onPress: () => void; disabled: boolean }) {
    const colors = useMentorPalette()
    return <Pressable accessibilityRole="radio" accessibilityLabel={title} accessibilityHint={description} accessibilityState={{ checked: selected, disabled }} disabled={disabled} onPress={onPress}
        style={({ pressed }) => [styles.card, { backgroundColor: selected ? colors.mint : colors.surface, borderColor: selected ? colors.greenBright : colors.border, opacity: pressed ? 0.8 : 1 }]}>
        {icon ? <View style={[styles.icon, { backgroundColor: selected ? colors.surface : colors.soft }]}><MentorQuestionIcon name={icon} color={colors.green} /></View> : null}
        <View style={styles.copy}><Text style={[styles.title, { color: colors.text }]}>{title}</Text>{description ? <Text style={[styles.description, { color: colors.muted }]}>{description}</Text> : null}</View>
        <View style={[styles.radio, { borderColor: selected ? colors.greenBright : colors.border }]}>{selected ? <View style={[styles.dot, { backgroundColor: colors.greenBright }]} /> : null}</View>
    </Pressable>
}

const styles = StyleSheet.create({
    card: { minHeight: 76, borderWidth: 1.5, borderRadius: 20, flexDirection: "row", alignItems: "center", padding: 16, gap: 12, flexGrow: 1, flexShrink: 1, flexBasis: "auto" },
    icon: { width: 42, height: 42, borderRadius: 14, justifyContent: "center", alignItems: "center" },
    copy: { flex: 1, minWidth: 0, gap: 5 }, title: { fontSize: 17, lineHeight: 23, fontWeight: "700" }, description: { fontWeight: "500", fontSize: 13, lineHeight: 19 },
    radio: { width: 21, height: 21, borderRadius: 11, borderWidth: 1.5, justifyContent: "center", alignItems: "center" }, dot: { width: 11, height: 11, borderRadius: 6 },
})
