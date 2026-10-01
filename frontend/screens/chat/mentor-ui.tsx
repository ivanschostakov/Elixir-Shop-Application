import { useRef } from "react"
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View, type StyleProp, type TextStyle } from "react-native"
import Svg, { Circle, Path, Rect } from "react-native-svg"
import { useChatFormFocus } from "@/screens/chat/chat-form-focus"
import { useTheme } from "@/providers/theme-provider"

export function useMentorPalette() {
    const { isDark } = useTheme()
    return isDark
        ? { green: "#8AD4AF", greenBright: "#31855E", text: "#EDF7F0", muted: "#A3B8AB", soft: "#203B30", mint: "#1C3D2E", surface: "#142A21", border: "#355144", blue: "#64B7FF" }
        : { green: "#1C694B", greenBright: "#38976A", text: "#202923", muted: "#7D8781", soft: "#F0F6F1", mint: "#E8F5EC", surface: "#FFFFFF", border: "#DDE6DF", blue: "#138DE5" }
}
export type MentorIconName = "leaf" | "plus" | "workout" | "book" | "smile" | "progress" | "adjust" | "calendar" | "food" | "more" | "back" | "chat" | "profile" | "settings" | "clock" | "camera" | "search"
export function MentorIcon({ name, size = 22, color = "#1C694B" }: { name: MentorIconName; size?: number; color?: string }) {
    const paths: Partial<Record<MentorIconName, string>> = {
        plus: "M12 3v18M3 12h18", workout: "M8 12h8M5 6v12M8 5v14M16 5v14M19 6v12M2 9v6M22 9v6",
        book: "M12 5v16M12 5C8 2 4 3 2 4v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-2-1-6-2-10 1Z",
        smile: "M8 14c2 3 6 3 8 0M8 9h.01M16 9h.01", adjust: "M2 5h5m4 0h11M2 12h11m4 0h5M2 19h3m4 0h13",
        calendar: "M7 2v5M17 2v5M3 10h18M7 14h2m3 0h2m3 0h.01M7 18h2m3 0h2",
        food: "M4 3v6c0 3 6 3 6 0V3M7 3v18M17 3c-3 3-3 9 0 9h3M20 3v18", back: "m14 5-7 7 7 7",
        chat: "M21 11a9 9 0 0 1-9 9H4l-3 2 1-7a9 9 0 1 1 19-4ZM7 10h10M7 14h6",
        profile: "M3 21v-2a7 7 0 0 1 14 0v2", settings: "m9 3 1-2h4l1 2 3 2 2 1v4l-2 1-1 3v3l-3 2-2-1H9l-2 1-3-2v-3l-1-3-2-1V6l2-1 3-2Z",
        clock: "M12 6v6l4 2", camera: "M8 5 9 2h6l1 3h5v15H3V5Z", search: "m16 16 5 5",
    }
    return <View style={{ width: size, height: size, flexShrink: 0 }}><Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" accessible={false}>
        {name === "leaf" ? <><Path d="M6 22C12 17 13 9 18 2" stroke="#608F38" /><Path d="M14 10C12 5 15 2 19 1c1 4-1 7-5 9ZM12 14c0-5-4-7-7-7 0 4 2 7 7 7ZM10 18c-1-4-4-5-8-4 1 4 4 5 8 4ZM14 13c1-4 4-5 8-5-1 4-3 6-8 5ZM11 18c2-3 5-3 8-2-2 3-4 4-8 2Z" fill="#69A335" stroke="none" /></> : null}
        {paths[name] ? <Path d={paths[name]} /> : null}
        {name === "progress" ? <><Rect x={3} y={13} width={4} height={9} rx={1} fill={color} stroke="none" /><Rect x={10} y={8} width={4} height={14} rx={1} fill={color} stroke="none" /><Rect x={17} y={2} width={4} height={20} rx={1} fill={color} stroke="none" /></> : null}
        {name === "smile" || name === "clock" ? <Circle cx={12} cy={12} r={10} /> : null}
        {name === "calendar" ? <Rect x={3} y={5} width={18} height={17} rx={2} /> : null}
        {name === "adjust" ? <><Circle cx={9} cy={5} r={2} /><Circle cx={15} cy={12} r={2} /><Circle cx={7} cy={19} r={2} /></> : null}
        {name === "more" ? [4, 12, 20].map(cx => <Circle key={cx} cx={cx} cy={12} r={1.6} fill={color} stroke="none" />) : null}
        {name === "profile" ? <Circle cx={10} cy={6} r={4} /> : null}
        {name === "settings" || name === "camera" ? <Circle cx={12} cy={12} r={4} /> : null}
        {name === "search" ? <Circle cx={10} cy={10} r={7} /> : null}
    </Svg></View>
}
export function MentorText({ children, muted = false, heading = false, style }: { children: React.ReactNode; muted?: boolean; heading?: boolean; style?: StyleProp<TextStyle> }) {
    const colors = useMentorPalette()
    return <Text style={[{ color: muted ? colors.muted : colors.text, fontSize: heading ? 22 : 16, lineHeight: heading ? 29 : 24, fontWeight: heading ? "600" : "400", flexShrink: 1 }, style]}>{children}</Text>
}
export function MentorButton({ label, onPress, disabled, primary, compact, icon }: { label: string; onPress: () => void; disabled?: boolean; primary?: boolean; compact?: boolean; icon?: React.ReactNode }) {
    const colors = useMentorPalette()
    return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled }} disabled={disabled} onPress={onPress} style={({ pressed }) => [mentorStyles.button, compact ? { flex: 1, paddingHorizontal: 6, gap: 5 } : null, { backgroundColor: primary ? colors.greenBright : colors.soft, opacity: disabled ? 0.45 : pressed ? 0.76 : 1 }]}>{icon}<Text style={{ color: primary ? "#FFFFFF" : colors.green, fontSize: compact ? 12.5 : 15, lineHeight: compact ? 19 : 21, fontWeight: "600", flexShrink: 1, textAlign: "center" }}>{label}</Text></Pressable>
}
export function MentorField({ label, value, onChange, numeric, disabled }: { label: string; value: unknown; onChange: (text: string) => void; numeric?: boolean; disabled?: boolean }) {
    const colors = useMentorPalette()
    const inputRef = useRef<TextInput | null>(null)
    const onFieldFocus = useChatFormFocus()
    return <View style={{ gap: 5, flexGrow: 1, flexBasis: 100 }}><MentorText muted>{label}</MentorText><TextInput ref={inputRef} onFocus={() => onFieldFocus?.(inputRef.current)} onBlur={() => onFieldFocus?.(null)} accessibilityLabel={label} editable={!disabled} value={value == null ? "" : String(value)} onChangeText={onChange} keyboardType={numeric ? "decimal-pad" : "default"} style={[mentorStyles.input, { color: colors.text, backgroundColor: colors.soft, borderColor: colors.border }]} /></View>
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
    input: { minHeight: 48, borderWidth: 1, borderRadius: 12, padding: 12, fontSize: 16 },
    tabs: { flexDirection: "row", gap: 6, alignItems: "stretch" },
    tab: { flex: 1, minWidth: 0, minHeight: 46, borderRadius: 14, paddingVertical: 10, paddingHorizontal: 5, justifyContent: "center" },
    metric: { flexGrow: 1, minWidth: 85, gap: 4, paddingVertical: 8 },
    notice: { padding: 16, borderRadius: 18, gap: 10 },
    header: { flexDirection: "row", alignItems: "center", gap: 9 },
    avatar: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center" },
    heading: { fontSize: 16, lineHeight: 23, fontWeight: "600", flex: 1 },
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
