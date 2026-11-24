import type { ReactNode } from "react"
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native"
import { Picker } from "@react-native-picker/picker"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { MentorHomeHeader } from "@/screens/chat/mentor-home"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import Check from "@/assets/icons/mentor/check.svg"
import Dumbbell from "@/assets/icons/mentor/dumbbell.svg"
import Pencil from "@/assets/icons/mentor/pencil-line.svg"
import Camera from "@/assets/icons/mentor/camera.svg"
import Close from "@/assets/icons/mentor/x.svg"
import Left from "@/assets/icons/mentor/chevron-left.svg"
import Right from "@/assets/icons/mentor/chevron-right.svg"

export function TrainingIcon({ name, size = 22, color }: { name: "check" | "workout" | "edit" | "photo" | "close" | "left" | "right"; size?: number; color?: string }) {
    const colors = useMentorPalette()
    const Icon = { check: Check, workout: Dumbbell, edit: Pencil, photo: Camera, close: Close, left: Left, right: Right }[name]
    return <Icon width={size} height={size} color={color ?? colors.green} accessible={false} />
}
export function TrainingAction({ label, onPress, secondary, disabled, busy, testID }: { label: string; onPress: () => void; secondary?: boolean; disabled?: boolean; busy?: boolean; testID?: string }) {
    const colors = useMentorPalette()
    return <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled || !!busy, busy }} disabled={disabled || busy} onPress={onPress} style={({ pressed }) => [secondary ? trainingStyles.textAction : trainingStyles.primary, { backgroundColor: secondary ? "transparent" : colors.greenBright, opacity: disabled || busy ? 0.45 : pressed ? 0.75 : 1 }]}>
        {busy ? <ActivityIndicator color={secondary ? colors.green : "#FFFFFF"} /> : null}<Text style={[secondary ? trainingStyles.textActionLabel : trainingStyles.primaryLabel, { color: secondary ? colors.green : "#FFFFFF" }]}>{label}</Text>
    </Pressable>
}
export function TrainingChoice({ label, selected, onPress, disabled, pill }: { label: string; selected: boolean; onPress: () => void; disabled?: boolean; pill?: boolean }) {
    const colors = useMentorPalette()
    return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ selected, disabled: !!disabled }} disabled={disabled} onPress={onPress} style={({ pressed }) => [pill ? trainingStyles.pill : trainingStyles.choice, { backgroundColor: pill ? selected ? colors.greenBright : colors.input : selected ? colors.input : "transparent", borderBottomColor: colors.border, opacity: disabled ? 0.45 : pressed ? 0.75 : 1 }]}>
        <Text style={[trainingStyles.choiceLabel, pill && { fontSize: 14, textAlign: "center" }, { color: pill && selected ? "#FFFFFF" : colors.text }]}>{label}</Text>{!pill && selected ? <TrainingIcon name="check" /> : null}
    </Pressable>
}
export function TrainingField({ label, value, onChange, multiline, numeric, disabled, placeholder, labeled, maxLength = 200 }: { label: string; value: string; onChange: (value: string) => void; multiline?: boolean; numeric?: boolean; disabled?: boolean; placeholder?: string; labeled?: boolean; maxLength?: number }) {
    const colors = useMentorPalette()
    const input = <TextInput accessibilityLabel={label} value={value} onChangeText={onChange} placeholder={placeholder ?? label} placeholderTextColor={colors.muted} editable={!disabled} multiline={multiline} textAlignVertical={multiline ? "top" : "center"} keyboardType={numeric ? "decimal-pad" : "default"} maxLength={maxLength} selectionColor={colors.greenBright} style={[trainingStyles.input, multiline && trainingStyles.textarea, { backgroundColor: colors.input, color: colors.text }]} />
    return labeled ? <View style={{ gap: 6 }}><Text style={[trainingStyles.caption, { color: colors.muted }]}>{label}</Text>{input}</View> : input
}
export function TrainingDurationPicker({ minutes, onChange, minMinutes = 15, maxMinutes = 180, optional = false, disabled = false }: { minutes: number | null; onChange: (minutes: number | null) => void; minMinutes?: number; maxMinutes?: number; optional?: boolean; disabled?: boolean }) {
    const colors = useMentorPalette()
    const value = minutes ?? minMinutes, hours = Math.floor(value / 60), remainder = value % 60
    const firstHour = Math.floor(minMinutes / 60), lastHour = Math.floor(maxMinutes / 60)
    const minuteBounds = (hour: number) => [Math.max(0, minMinutes - hour * 60), Math.min(59, maxMinutes - hour * 60)] as const
    const [firstMinute, lastMinute] = minuteBounds(hours)
    const wheelStyle = { flex: 1, height: Platform.OS === "ios" ? 180 : 54, color: colors.text }
    return <View style={{ flexDirection: "row", alignItems: "center", backgroundColor: colors.input, borderRadius: 18, overflow: "hidden" }}>
        <Picker accessibilityLabel={mt("Часы")} enabled={!disabled} selectedValue={optional && minutes == null ? -1 : hours} mode="dropdown" style={wheelStyle} itemStyle={{ color: colors.text, fontSize: 21, fontWeight: "600" }} onValueChange={value => {
            const hour = Number(value)
            if (optional && hour === -1) { onChange(null); return }
            if (!Number.isInteger(hour) || hour < firstHour || hour > lastHour) return
            const [first, last] = minuteBounds(hour)
            onChange(hour * 60 + Math.max(first, Math.min(last, minutes == null ? 0 : remainder)))
        }}>
            {optional ? <Picker.Item label={mt("Не указано")} value={-1} /> : null}
            {Array.from({ length: lastHour - firstHour + 1 }, (_, index) => index + firstHour).map(hour => <Picker.Item key={hour} label={mt("{0} ч", [hour])} value={hour} />)}
        </Picker>
        <Picker accessibilityLabel={mt("Минуты")} enabled={!disabled && !(optional && minutes == null) && firstMinute !== lastMinute} selectedValue={optional && minutes == null ? -1 : remainder} mode="dropdown" style={wheelStyle} itemStyle={{ color: colors.text, fontSize: 21, fontWeight: "600" }} onValueChange={value => {
            const minute = Number(value)
            if (Number.isInteger(minute) && minute >= firstMinute && minute <= lastMinute) onChange(hours * 60 + minute)
        }}>
            {optional && minutes == null ? <Picker.Item label="—" value={-1} /> : Array.from({ length: lastMinute - firstMinute + 1 }, (_, index) => index + firstMinute).map(minute => <Picker.Item key={minute} label={mt("{0} мин", [minute])} value={minute} />)}
        </Picker>
    </View>
}
export function TrainingHeading({ title, subtitle }: { title: string; subtitle?: string }) {
    const colors = useMentorPalette()
    return <View style={{ gap: 6 }}><Text accessibilityRole="header" style={[trainingStyles.title, { color: colors.text }]}>{title}</Text>{subtitle ? <Text style={[trainingStyles.subtitle, { color: colors.muted }]}>{subtitle}</Text> : null}</View>
}
export function TrainingFrame({ title, onBack, children, footer }: { title: string; onBack: () => void; children: ReactNode; footer: ReactNode }) {
    const colors = useMentorPalette(), insets = useSafeAreaInsets()
    return <View style={[trainingStyles.screen, { backgroundColor: colors.surface, paddingTop: insets.top }]}><MentorHomeHeader title={title} onBack={onBack} />{children}<View style={[trainingStyles.footer, { paddingBottom: Math.max(insets.bottom, 12) }]}>{footer}</View></View>
}
export const trainingStyles = StyleSheet.create({
    screen: { flex: 1, minHeight: 0 }, body: { width: "100%", maxWidth: 560, alignSelf: "center", paddingHorizontal: 22, paddingTop: 14, paddingBottom: 22, gap: 22 }, fill: { flex: 1, minHeight: 0 },
    title: { fontSize: 32, lineHeight: 38, fontWeight: "800", letterSpacing: -0.8 }, subtitle: { fontSize: 16, lineHeight: 23, fontWeight: "500" }, section: { fontSize: 22, lineHeight: 28, fontWeight: "700" },
    row: { flexDirection: "row", alignItems: "center", gap: 12 }, spread: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 10 },
    primary: { minHeight: 54, borderRadius: 18, paddingHorizontal: 16, paddingVertical: 14, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10 }, primaryLabel: { fontSize: 18, lineHeight: 24, fontWeight: "700", textAlign: "center", flexShrink: 1 },
    textAction: { minHeight: 44, justifyContent: "center", alignItems: "center", paddingHorizontal: 8, flexDirection: "row", gap: 8 }, textActionLabel: { fontSize: 16, lineHeight: 22, fontWeight: "600", textAlign: "center", flexShrink: 1 },
    footer: { paddingTop: 10, paddingHorizontal: 22, gap: 5, width: "100%", maxWidth: 560, alignSelf: "center" },
    choice: { minHeight: 54, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 13, flexDirection: "row", alignItems: "center", gap: 12, borderBottomWidth: StyleSheet.hairlineWidth }, choiceLabel: { flex: 1, fontSize: 17, lineHeight: 23, fontWeight: "600" },
    pill: { flex: 1, minHeight: 46, borderRadius: 14, paddingHorizontal: 9, paddingVertical: 10, flexDirection: "row", alignItems: "center" },
    input: { minHeight: 50, paddingHorizontal: 14, paddingVertical: 12, borderRadius: 14, fontSize: 17, lineHeight: 24, fontWeight: "500" }, textarea: { height: 194 }, caption: { fontSize: 13, lineHeight: 19 },
    progress: { flexDirection: "row", gap: 5, marginTop: 8 }, segment: { flex: 1, height: 5, borderRadius: 3 },
    iconButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" }, listRow: { minHeight: 66, paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth, flexDirection: "row", alignItems: "center", gap: 12 }, listTitle: { fontSize: 17, lineHeight: 23, fontWeight: "700", flexShrink: 1 }, listValue: { fontSize: 16, lineHeight: 22, fontWeight: "600" },
    photo: { flex: 1, minWidth: 0, gap: 8 }, photoSlot: { height: 170, borderRadius: 18, alignItems: "center", justifyContent: "center", overflow: "hidden" }, photoImage: { width: "100%", height: "100%" }, photoLabel: { textAlign: "center", fontSize: 13, lineHeight: 18 },
    day: { flex: 1, alignItems: "center", gap: 6 }, dayButton: { height: 38, width: 38, borderRadius: 19, alignItems: "center", justifyContent: "center" }, dot: { height: 4, width: 4, borderRadius: 2 },
})
