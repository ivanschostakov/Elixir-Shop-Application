import { useState } from "react"
import { Keyboard, Modal, Platform, Pressable, StyleSheet, Text, View } from "react-native"
import DateTimePicker, { DateTimePickerAndroid, type DateTimePickerEvent } from "@react-native-community/datetimepicker"
import { AppPickerPanel } from "@/components/platform/app-picker"

export function AppTimePicker({ label, value, onChange, disabled, locale, dark, colors }: {
    label: string; value: string; onChange: (value: string) => void; disabled: boolean; locale: string; dark: boolean
    colors: { surface: string; border: string; text: string; greenBright: string; muted: string }
}) {
    const [draft, setDraft] = useState<Date | null>(null)
    const commit = (date: Date) => onChange([date.getHours(), date.getMinutes()].map(part => String(part).padStart(2, "0")).join(":"))
    const open = () => {
        Keyboard.dismiss()
        // Keep the wall-clock selection independent of today's DST transition.
        const [hour, minute] = value.split(":").map(Number)
        const selected = new Date(2000, 0, 15, hour, minute)
        if (Platform.OS === "ios") setDraft(selected)
        else if (Platform.OS === "android") DateTimePickerAndroid.open({
            value: selected, mode: "time", is24Hour: true,
            onChange: (event: DateTimePickerEvent, date?: Date) => { if (event.type === "set" && date) commit(date) },
        })
    }
    const trigger = <Pressable accessibilityRole="button" accessibilityLabel={label + ", " + value} accessibilityState={{ disabled }} disabled={disabled || Platform.OS === "web"} onPress={open}
        style={({ pressed }) => [styles.button, { backgroundColor: dark ? "#263A31" : "#EAF3ED", opacity: disabled ? 0.5 : pressed ? 0.7 : 1 }]}>
        <Text style={[styles.time, { color: dark ? "#B9E7C9" : "#235C42" }]}>{value}</Text>
    </Pressable>
    if (!draft) return trigger
    return <>{trigger}<Modal animationType="slide" transparent visible onRequestClose={() => setDraft(null)}>
        <AppPickerPanel title={label} onCancel={() => setDraft(null)} onConfirm={() => { commit(draft); setDraft(null) }}>
            <View style={[styles.wheel, { backgroundColor: colors.surface }]}>
                <DateTimePicker testID={`mentor-native-time-${label}`} accessibilityLabel={label} value={draft} mode="time" display="spinner"
                    locale={locale.startsWith("en") ? "en-GB" : locale} themeVariant={dark ? "dark" : "light"} textColor={colors.text} accentColor={colors.greenBright}
                    style={styles.picker} onChange={(event, date) => { if (event.type === "set" && date) setDraft(date) }} />
            </View>
        </AppPickerPanel>
    </Modal></>
}
const styles = StyleSheet.create({
    button: { alignSelf: "flex-end", minHeight: 44, minWidth: 78, paddingHorizontal: 12, borderRadius: 14, alignItems: "center", justifyContent: "center" },
    time: { fontSize: 19, fontWeight: "700", letterSpacing: 0.3, fontVariant: ["tabular-nums"] },
    wheel: { alignItems: "center", borderRadius: 18, overflow: "hidden" }, picker: { width: "100%", height: 200 },
})
