import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native"
import { useTheme } from "@/providers/theme-provider"

export function MentorText({ children, muted = false, heading = false }: { children: React.ReactNode; muted?: boolean; heading?: boolean }) {
    const { palette } = useTheme()
    return <Text style={{ color: muted ? palette.mutedText : palette.text, fontSize: heading ? 20 : 15, lineHeight: heading ? 27 : 22, fontWeight: heading ? "700" : "400", flexShrink: 1 }}>{children}</Text>
}
export function MentorButton({ label, onPress, disabled, primary, icon }: { label: string; onPress: () => void; disabled?: boolean; primary?: boolean; icon?: React.ReactNode }) {
    const { palette } = useTheme()
    return <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={disabled} onPress={onPress} style={[mentorStyles.button, { backgroundColor: primary ? "#176B4A" : palette.surfaceMuted, opacity: disabled ? 0.45 : 1 }]}>{icon}<Text style={{ color: primary ? "#FFFFFF" : palette.text, fontSize: 15, fontWeight: "600", flexShrink: 1 }}>{label}</Text></Pressable>
}
export function MentorField({ label, value, onChange, numeric, disabled }: { label: string; value: unknown; onChange: (text: string) => void; numeric?: boolean; disabled?: boolean }) {
    const { palette } = useTheme()
    return <View style={{ gap: 4, flexGrow: 1, flexBasis: 100 }}><MentorText muted>{label}</MentorText><TextInput accessibilityLabel={label} editable={!disabled} value={value == null ? "" : String(value)} onChangeText={onChange} keyboardType={numeric ? "decimal-pad" : "default"} style={[mentorStyles.input, { color: palette.text, backgroundColor: palette.fieldBackground, borderColor: palette.border }]} /></View>
}
export function MentorTabs<T extends string>({ items, value, onChange }: { items: Record<T, string>; value: T | null; onChange: (value: T) => void }) {
    const { palette } = useTheme()
    const scrolling = Object.keys(items).length > 4
    const tabs = <View accessibilityRole="tablist" style={mentorStyles.tabs}>{(Object.keys(items) as T[]).map(key => <Pressable key={key} accessibilityRole="tab" accessibilityState={{ selected: value === key }} onPress={() => onChange(key)} style={[mentorStyles.tab, scrolling ? { minWidth: 90, flex: 0 } : null, { borderBottomColor: value === key ? "#27855F" : "transparent" }]}><Text style={{ color: value === key ? palette.primary : palette.mutedText, fontSize: 12, fontWeight: "600", textAlign: "center", flexShrink: 1 }}>{items[key]}</Text></Pressable>)}</View>
    return scrolling ? <ScrollView horizontal showsHorizontalScrollIndicator={false}>{tabs}</ScrollView> : tabs
}
export const mentorStyles = StyleSheet.create({
    body: { padding: 16, gap: 16, width: "100%", maxWidth: 760, alignSelf: "center" },
    section: { gap: 12, paddingVertical: 12, borderTopWidth: StyleSheet.hairlineWidth, borderColor: "#84958D66" },
    row: { flexDirection: "row", flexWrap: "wrap", gap: 10, alignItems: "center" },
    button: { minHeight: 48, borderRadius: 8, paddingHorizontal: 14, paddingVertical: 12, flexDirection: "row", gap: 8, alignItems: "center", justifyContent: "center", maxWidth: "100%" },
    input: { minHeight: 46, borderWidth: 1, borderRadius: 8, padding: 10, fontSize: 16 },
    tabs: { flexDirection: "row", flexWrap: "wrap", gap: 2, alignItems: "stretch" },
    tab: { flex: 1, minWidth: 55, minHeight: 48, paddingVertical: 10, paddingHorizontal: 3, justifyContent: "center", borderBottomWidth: 2 },
    metric: { flexGrow: 1, minWidth: 110, gap: 4, paddingVertical: 8 },
})
