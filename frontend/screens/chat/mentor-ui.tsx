import { useRef } from "react"
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View, type StyleProp, type TextStyle } from "react-native"
import { MentorQuestionIcon, type MentorQuestionIconName } from "@/screens/chat/mentor-question-icon"
import { useChatFormFocus } from "@/screens/chat/chat-form-focus"
import { useTheme } from "@/providers/theme-provider"

export function useMentorPalette() {
    const { isDark } = useTheme()
    return isDark
        ? { green: "#8AD4AF", greenBright: "#31855E", text: "#EDF7F0", muted: "#A3B8AB", soft: "#203B30", mint: "#1C3D2E", surface: "#142A21", border: "#355144", blue: "#64B7FF" }
        : { green: "#1C694B", greenBright: "#38976A", text: "#202923", muted: "#7D8781", soft: "#F0F6F1", mint: "#E8F5EC", surface: "#FFFFFF", border: "#DDE6DF", blue: "#138DE5" }
}
export type MentorIconName = "leaf" | "plus" | "workout" | "book" | "smile" | "progress" | "adjust" | "calendar" | "food" | "more" | "back" | "chat" | "profile" | "settings" | "clock" | "camera" | "search" | "scale"
export function MentorIcon({ name, size = 22, color }: { name: MentorIconName; size?: number; color?: string }) {
    const colors = useMentorPalette()
    const aliases: Record<MentorIconName, MentorQuestionIconName> = { leaf: "leaf", plus: "plus", workout: "gym", book: "book", smile: "maintain", progress: "progress", adjust: "adjust", calendar: "weekly", food: "food", more: "more", back: "back", chat: "message", profile: "profile", settings: "settings", clock: "clock", camera: "camera", search: "search", scale: "weight" }
    return <MentorQuestionIcon name={aliases[name]} size={size} color={color ?? colors.green} />
}

export function MentorText({ children, muted = false, heading = false, style }: { children: React.ReactNode; muted?: boolean; heading?: boolean; style?: StyleProp<TextStyle> }) {
    const colors = useMentorPalette()
    return <Text style={[{ color: muted ? colors.muted : colors.text, fontSize: heading ? 22 : 16, lineHeight: heading ? 29 : 24, fontWeight: heading ? "700" : "500", flexShrink: 1 }, style]}>{children}</Text>
}
export function MentorButton({ label, onPress, disabled, primary, compact, icon }: { label: string; onPress: () => void; disabled?: boolean; primary?: boolean; compact?: boolean; icon?: React.ReactNode }) {
    const colors = useMentorPalette()
    return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled }} disabled={disabled} onPress={onPress} style={({ pressed }) => [mentorStyles.button, compact ? { flex: 1, paddingHorizontal: 6, gap: 5 } : null, { backgroundColor: primary ? colors.greenBright : colors.soft, opacity: disabled ? 0.45 : pressed ? 0.76 : 1 }]}>{icon}<Text style={{ color: primary ? "#FFFFFF" : colors.green, fontSize: compact ? 12.5 : 15, lineHeight: compact ? 19 : 21, fontWeight: "700", flexShrink: 1, textAlign: "center" }}>{label}</Text></Pressable>
}
export function MentorField({ label, value, onChange, numeric, disabled }: { label: string; value: unknown; onChange: (text: string) => void; numeric?: boolean; disabled?: boolean }) {
    const colors = useMentorPalette()
    const inputRef = useRef<TextInput | null>(null)
    const onFieldFocus = useChatFormFocus()
    return <View style={{ gap: 5, flexGrow: 1, flexBasis: 100 }}><MentorText muted>{label}</MentorText><TextInput ref={inputRef} onFocus={() => onFieldFocus?.(inputRef.current)} onBlur={() => onFieldFocus?.(null)} accessibilityLabel={label} editable={!disabled} value={value == null ? "" : String(value)} onChangeText={text => onChange(numeric ? text.replace(/,/g, ".") : text)} keyboardType={numeric ? "decimal-pad" : "default"} style={[mentorStyles.input, { color: colors.text, backgroundColor: colors.soft, borderColor: colors.border }]} /></View>
}
export function MentorTabs<T extends string>({ items, value, onChange }: { items: Record<T, string>; value: T | null; onChange: (value: T) => void }) {
    const colors = useMentorPalette()
    const scrolling = Object.keys(items).length > 4
    const tabs = <View accessibilityRole="tablist" style={mentorStyles.tabs}>{(Object.keys(items) as T[]).map(key => <Pressable key={key} accessibilityRole="tab" accessibilityState={{ selected: value === key }} onPress={() => onChange(key)} style={({ pressed }) => [mentorStyles.tab, scrolling ? { minWidth: 90, flex: 0 } : null, { backgroundColor: value === key ? colors.greenBright : colors.soft, opacity: pressed ? 0.7 : 1 }]}><Text style={{ color: value === key ? "#FFFFFF" : colors.muted, fontSize: 14, lineHeight: 20, textAlign: "center", flexShrink: 1 }}>{items[key]}</Text></Pressable>)}</View>
    return scrolling ? <ScrollView horizontal showsHorizontalScrollIndicator={false}>{tabs}</ScrollView> : tabs
}
export const mentorStyles = StyleSheet.create({
    body: { padding: 16, gap: 16, width: "100%", maxWidth: 700, alignSelf: "center", borderRadius: 24 },
    section: { gap: 12, paddingVertical: 16, borderTopWidth: StyleSheet.hairlineWidth, borderColor: "#84958D33" },
    row: { flexDirection: "row", flexWrap: "wrap", gap: 10, alignItems: "center" },
    button: { minHeight: 48, borderRadius: 13, paddingHorizontal: 12, paddingVertical: 12, flexDirection: "row", gap: 8, alignItems: "center", justifyContent: "center", maxWidth: "100%" },
    input: { fontWeight: "500", minHeight: 48, borderWidth: 1, borderRadius: 12, padding: 12, fontSize: 16 },
    tabs: { flexDirection: "row", gap: 6, alignItems: "stretch" },
    tab: { flex: 1, minWidth: 0, minHeight: 46, borderRadius: 14, paddingVertical: 10, paddingHorizontal: 5, justifyContent: "center" },
    metric: { flexGrow: 1, minWidth: 85, gap: 4, paddingVertical: 8 },
    notice: { padding: 16, borderRadius: 18, gap: 10 },
    header: { flexDirection: "row", alignItems: "center", gap: 9, minHeight: 36 },
    avatar: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center" },
    heading: { fontSize: 16, lineHeight: 23, fontWeight: "700", flex: 1 },
    time: { fontSize: 12, lineHeight: 18 },
    greeting: { fontSize: 18, lineHeight: 26, marginBottom: 7 },
    plan: { gap: 0, marginBottom: 8 },
    planLine: { fontSize: 16, lineHeight: 22 },
    actions: { gap: 9 },
    actionRow: { flexDirection: "row", alignItems: "stretch", gap: 9 },
    actionCell: { flex: 1 },
    navigation: { flexDirection: "row", gap: 6, alignItems: "center" },
    navigationPill: { flex: 1, minWidth: 44, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center" },
})
